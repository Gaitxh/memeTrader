# Profit-First Autonomous Meme Trading System — Research, Architecture and Forward Experiment Plan

Date: 2026-09-04
Owner: Lead ChatGPT research/review; Codex remains the single implementation/test/deploy owner
Status: `AUTHORITATIVE_RESEARCH_DELTA / IMPLEMENT_IN_ORDER / LIVE_LOCKED`

## 1. Executive decision

The present `chain-meme-trader/v4` is valuable forward evidence, but its 12 rows are cumulative historical stages, not 12 independent complete trading policies. Stage 1–7 share the same high momentum/liquidity base gate; later stages add progressively stricter execution/rug/focus gates. The UI therefore overstates strategy diversity, and the design cannot answer the user's main questions:

1. Are strict entry gates suppressing profitable opportunity volume?
2. Can risky or later-rugged tokens still be profitable when exited early?
3. Which contemporaneous flow/route/pool features warn of a local top or imminent failure?
4. Does post-buy information research improve holding decisions after all costs?
5. Can the same decision/execution pipeline later support real trading without rewriting the product?

Decision: preserve all v4 registrations, decisions, positions, trades and outcomes. Stop only **new v4 enrollment** at a new immutable frontier after v5 is ready; continue monitoring and closing existing v4 positions. Build `chain-meme-trader/v5` as independent complete policy accounts on a shared event/market/execution kernel. Do not backfill v5.

The key operating principle is:

> Entry should maximize opportunity recall under bounded Paper risk; exit should be fast, deterministic and execution-aware. What remains strict is time, identity, actual route semantics, append-only accounting and version isolation—not a universal wall of safety thresholds.

## 2. What is retained from the current system

The following are production-quality foundations and must be reused rather than rebuilt:

- strict-forward registration and activation boundaries;
- immutable launch facts and exact token/pool lineage;
- separation of Holding Surface Safety from Jupiter Execution Route Truth;
- direct SPL/Token-2022 mint capability inspection;
- amount-specific 20 USDC Jupiter BUY and immediate acquired-quantity SELL preflight;
- exact held pool/base vault/quote vault/mint/LP-mint monitoring;
- confirmed-rug terminal semantics: exact account alert plus full-remaining economic failure, one final escape attempt, then writeoff and permanent no-rearm/no-reentry for that surface/version;
- exact-remaining executable valuation, unknown rather than fabricated PNL when a fresh full-size quote is absent;
- append-only Paper evidence and browser reads that never issue provider/RPC requests.

These are shared infrastructure facts. They must no longer be presented as if each additional fact automatically defines a new strategy.

## 3. Corrections to tempting but unsafe simplifications

### 3.1 Flat price is a warning, not pool-death proof

A removed pool often leaves an apparently frozen external price, but provider staleness, API failure and genuinely inactive trading can look identical. Separate:

- `DATA_STALE`: the collector/provider has not advanced;
- `MARKET_STALLED`: chain slots advance but this market has no trades/price movement relative to its prior intensity;
- `SELLABILITY_DEGRADED`: full-size executable recovery worsens or route disappears;
- `EXACT_ACCOUNT_ALERT`: pool/vault/mint facts changed materially;
- `DEAD_TERMINAL`: exact alert plus no economic full-size exit, followed by the frozen terminal action.

A stall may immediately arm an exit. It may not alone write off or permanently blacklist a surface.

### 3.2 “Sell at the local top” is not a future-price prediction task

The system cannot know the local maximum in advance. It can estimate whether continuation quality is deteriorating using only information available now. Evaluate a top-exit signal later against the maximum **time-valid executable full/partial-position recovery quote** in the frozen evaluation window, never against a later DEX ATH used as an earlier feature.

### 3.3 Wider entry does not mean imaginary execution

All Paper policies intended as executable candidates still require a fresh amount-specific BUY and a contemporaneous acquired-quantity SELL preflight. Recovery quality, canonical status, liquidity, creator history and concentration can vary by strategy and become soft/risk-tier features. An impossible transfer, invalid identity, terminal-dead surface or no BUY route is not a trade.

Very poor or absent initial SELL routes may still enter a separate `RESEARCH_ONLY / NOT_LIVE_ELIGIBLE` counterfactual ledger. They must not be counted as realistic Paper fills.

## 4. The 12 v5 complete strategy policies

Use three mutually defined entry estimands, each copied into four complete holding/exit policies. Each row is an independent virtual account and immutable policy definition.

### Entry family E1 — `LAUNCH_RECALL`

Purpose: increase early opportunity coverage and directly test whether existing safety/quality gates reject profitable launches.

- trigger: first strict local create/migration/market-frame opportunity in the registered age window;
- broad Paper eligibility: valid exact identity, fresh BUY route, acquired-quantity SELL preflight, no terminal dead-surface prohibition and no deterministically impossible transfer;
- canonical/noncanonical surface, creator history, liquidity, momentum, holder concentration, mint privileges and recovery ratio are frozen risk features, not automatically universal rejects;
- use stratified risk buckets and bounded admission so low-quality clones do not consume all quote capacity;
- explicitly mark `paper_exploration_only` when the policy is outside future Live eligibility.

### Entry family E2 — `FLOW_ACCELERATION`

Purpose: trade tokens whose actual transaction flow is accelerating, not merely whose 5-minute provider summary is high.

- trigger: first registered crossing using current-only trade intensity, quote-flow imbalance, buyer breadth growth, volume acceleration, reserve/liquidity path and executable recovery;
- no repeated entry for the same family/version after a terminal exit;
- current `_momentum_score` remains an immutable control feature, not the final model.

### Entry family E3 — `REAWAKENING`

Purpose: trade old markets that were genuinely dormant before a new burst.

- freeze a pre-trigger dormant baseline from locally observed history;
- require the baseline to predate the trigger; never label a token reawakening because a later price rise was observed;
- trigger from standardized increases in trade intensity, net quote flow, new buyers, volatility, liquidity/route recovery and price acceleration;
- keep launch and reawakening denominators separate even when the same mint later qualifies for both at different times.

### Four policy variants per entry family

1. `FAST_ESCAPE`
   - prioritizes survival and capital turnover;
   - early partial profit, tighter execution-aware trailing logic, fast flow-reversal exit;
   - intended to test the user's thesis that even risky/rug-prone launches can be profitable when escaped early.

2. `BALANCED_DYNAMIC`
   - deterministic reference policy;
   - hard safety exit, adaptive stop/trailing, staged take-profit, route/liquidity deterioration and maximum hold;
   - replaces the current coarse fixed percentages only through a new registered version, never in place.

3. `PEAK_GUARD`
   - same entry as its family siblings;
   - adds strictly current microstructure divergence: executable recovery makes a high while buy flow/buyer breadth/intensity deteriorates, sell-size concentration rises, trade gaps widen or route quality decays;
   - no ATH or future-window data enters the decision.

4. `AGENT_AUGMENTED`
   - exact same entry and mechanical hard exits as `BALANCED_DYNAMIC`;
   - one shared post-buy investigation case per token/cohort, not one case per strategy;
   - negative evidence may accelerate a soft exit after the result exists; positive evidence may only extend a bounded runner/trailing policy and can never override exact-account risk, no-route, hard stop or maximum hold;
   - until a treatment version is preregistered and has reliable assessment coverage, record advisory treatment decisions without changing the control fill.

Resulting accounts:

- S01–S04: `LAUNCH_RECALL × {FAST_ESCAPE, BALANCED_DYNAMIC, PEAK_GUARD, AGENT_AUGMENTED}`
- S05–S08: `FLOW_ACCELERATION × {FAST_ESCAPE, BALANCED_DYNAMIC, PEAK_GUARD, AGENT_AUGMENTED}`
- S09–S12: `REAWAKENING × {FAST_ESCAPE, BALANCED_DYNAMIC, PEAK_GUARD, AGENT_AUGMENTED}`

## 5. Hard execution contract versus strategy features

### Common hard contract for executable Paper policies

- all inputs have `observed_at`, `ingested_at`, `recorded_at/available_at <= decision_at`;
- exact chain/mint/market-surface identity;
- no dead-surface/no-reentry terminal for the policy version;
- fresh amount-specific BUY quote and explicit quote timing/route status;
- acquired minimum token output becomes the immediate full-size SELL-preflight input;
- deterministic impossible-transfer or invalid protocol state rejects;
- idempotent intent/attempt/fill lineage;
- exit work preempts entry/research quote work;
- every no-route, error, timeout, late response, writeoff and zero-yield case remains in the denominator.

### Features that must not remain one universal hard wall

- momentum score;
- provider liquidity threshold;
- immediate recovery percentage above mere sellability;
- canonical versus noncanonical PumpSwap status for high-risk Paper exploration;
- creator launch frequency;
- holder concentration;
- pool age inside the broader strategy-specific range;
- unverified but non-impossible mint privileges;
- social/narrative confidence.

Each strategy freezes how these affect eligibility, sampling, risk tier or holding. Future Live eligibility is a separate field and may remain much stricter.

## 6. Gate-ablation and opportunity-recall learning

Do not answer “the gate is too strict” by globally lowering it. Record each otherwise eligible candidate and run bounded one-variable-at-a-time counterfactuals:

- lower momentum bucket;
- lower liquidity bucket;
- lower immediate recovery bucket;
- noncanonical but exactly identified surface;
- concentrated/serial-creator bucket;
- incomplete optional safety evidence but valid transfer/route.

Share the same market frames and provider responses; do not issue 12 duplicate quote/research requests. Compare fixed-horizon and complete-position outcomes including no-route/writeoff. Report:

- incremental candidates and actual Paper admissions;
- net executable return after all known costs;
- writeoff/no-route frequency;
- maximum executable adverse excursion;
- capital time and quote-budget consumption;
- remove-best-1/remove-best-3 robustness.

Only one gate change enters a future live-candidate strategy version at a time.

## 7. Strict-forward market-state data factory

The present 5-minute provider aggregates and 15-second position scans are useful but too coarse for top formation. Build a shared `MarketFrame/v1` from PumpSwap transaction/account evidence.

### Raw/current-only inputs

- slot/block time and local receive time;
- exact pool base/quote vault balances and deltas;
- decoded buy/sell quote and base amounts;
- trade direction and inter-arrival times;
- distinct current-window buyer/seller addresses represented by salted/stable local IDs or aggregate counts, without exposing addresses to Agents/Web;
- first-time versus repeat buyer counts in the locally observed history;
- trade-size percentiles, largest trade share and top-k flow concentration;
- liquidity/reserve slope;
- fresh Jupiter full-position recovery, route status, route complexity and price impact;
- account-subscription health and source-gap flags.

### Derived horizons

Maintain incremental 1s/3s/5s/15s/60s features for held positions and short-lived entry candidates:

- price/recovery velocity and acceleration;
- buy/sell quote-flow imbalance;
- trade-intensity level and acceleration;
- buyer breadth growth/decay;
- large-sell pressure and concentration;
- recovery high-water mark and drawdown;
- liquidity/vault depletion slopes;
- divergence flags: new price/recovery high with weakening flow/breadth/intensity.

Keep the full-frequency ring buffer in memory. Persist immutable frames only at strategy decisions, exit evaluations, material state changes and registered fixed checkpoints. This preserves SQLite simplicity and avoids turning thousands of discovered tokens into an unbounded write stream.

### Collection path

Start with official Solana WebSocket account/log subscriptions and the Pump public IDL/event layout. Measure receive-to-frame latency, gaps and RPC cost. Escalate to a maintained Geyser/Yellowstone stream only if native WebSocket plus bounded transaction fetch cannot meet measured held-position latency; do not add infrastructure merely because it is fashionable.

## 8. Position risk and exit state machine

Use an event-driven deterministic state machine per physical/virtual position:

`GREEN -> WATCH -> EXIT_ARMED -> EXIT_QUOTING -> PARTIAL/EXIT_FILLED`

with orthogonal terminal states:

`DATA_STALE`, `EXACT_ACCOUNT_ALERT`, `DEAD_TERMINAL`, `WRITTEN_OFF`.

Priority order:

1. exact pool/vault/mint/LP-account emergency;
2. full-position route disappearance or abrupt recovery collapse;
3. hard loss/cost-basis protection;
4. flow reversal/top divergence;
5. staged profit-taking/trailing;
6. time decay/maximum hold.

`DATA_STALE` must escalate collection and conservatively arm an exit, but not by itself prove a rug. A high-risk event writes an immutable `ExitIntent` immediately; the next fresh exact-size quote determines Paper fill/retry. Critical exits always preempt entry, valuation and research quotes.

Adaptive observation cadence is state based, not a permanent provider flood:

- no position / low-priority candidate: slow aggregate observation;
- open `GREEN`: normal account stream plus bounded valuation;
- `WATCH`: higher-frequency local frame evaluation;
- `EXIT_ARMED`: immediate quote;
- exact account alert: highest-priority full-remaining exit path.

## 9. Unified Paper/Live execution kernel

New v5 strategies must not write a BUY trade directly from an admission decision. Use one explicit lifecycle:

`StrategyDecision -> OrderIntent -> ExecutionPlan -> ExecutionAttempt -> Fill -> PositionEvent -> ExitIntent -> Attempt -> Fill/Writeoff -> Settlement`

Minimum immutable records:

- `strategy_definitions/registrations`;
- `strategy_decisions`;
- `order_intents` with idempotency key, strategy support and available-at snapshot;
- `execution_plans` with quote/route/min-output/cost-completeness;
- `execution_attempts` before every provider or broker side effect;
- `fills` or explicit no-fill terminal;
- `position_events` and a reconstructable projection;
- `strategy_allocations` so multiple virtual strategies can share one future physical order while keeping independent Paper outcomes.

`PaperExecutionAdapter` consumes the same plan but does not sign/broadcast. It records at least two valuations:

- conservative minimum-output fill/recovery;
- central quote output with explicit cost-completeness.

A result with unknown network/priority/MEV cost is valid Paper evidence but is not `live_economics_complete`.

A future `LiveExecutionAdapter` may use the same plan only after separate review, simulation, signer isolation, small-capital chain test, confirmation and reconciliation. Private keys never enter config, SQLite, Web or Agent context. Live remains locked during this cycle.

## 10. Shared post-buy investigation, not 12× repeated Agents

Create one immutable `postbuy_investigation_case` per token/cohort. Deterministic local collectors assemble the evidence package first. At most two production Agent lanes run in parallel:

1. identity/narrative/diffusion: exact project identity, original source, independent reporting, community growth and impersonation;
2. adversarial/manipulation: creator/clone relationships, fake community, wash/pump indicators, contradictions and suspicious promotion.

Required result fields include evidence IDs/URLs already locally allowed, first-observed/available times, independent-origin count, contradiction status, confidence, urgent-negative flag and expiry. Free-form prose never directly submits an order.

The case is shared by all matching arms. Late results affect only evaluations after their available time. Agents never calculate price, pool balances, routes, PNL or numeric exits.

## 11. Continuous learning without online self-corruption

The live/current policy never retunes after a single winner or loser. The system continuously collects data, but policy changes follow:

`baseline -> shadow challenger -> preregistered Paper challenger -> maturity review -> new version -> forward activation`.

For each family/policy, retain intention-to-treat outcomes and report:

- closed and open sample counts by independent date/regime;
- conservative and central executable PNL;
- win rate, median, trimmed mean and capital-weighted return;
- maximum drawdown, expected shortfall/tail loss and writeoff rate;
- no-route duration and first-economic-exit latency;
- capital-time efficiency;
- top-1/top-3 contribution and remove-best robustness;
- outcome by risk bucket and rejected-gate counterfactual;
- Agent coverage/latency/abstention and incremental treatment effect only on exact paired entries.

Suggested maturity states, not Paper-admission blocks:

- `ENGINEERING_VALID`: >=10 entries and >=5 terminal exits;
- `DESCRIPTIVE`: >=30 closed across >=5 dates with both gains and losses;
- `PROVISIONAL_CHAMPION`: >=100 closed across >=15 dates, >=20 losses, tail/writeoff and remove-best checks;
- `CAPITAL_REVIEW`: substantially larger multi-regime evidence and separate execution-security review.

Use future outcomes only as labels/evaluation after their horizon matures. They never enter an earlier frame or decision. Keep chronological train/validation and sealed test boundaries for any later model.

## 12. Low-latency and workload architecture

One token/cohort should cause:

`1 shared source/event set -> 1 shared MarketFrame stream -> 1 shared BUY quote/preflight -> N local strategy decisions -> independent virtual allocations`.

Never:

`12 strategies -> 12 RPC subscriptions -> 12 Jupiter quotes -> 12 Agent calls`.

Use a single priority scheduler:

1. exact-account emergency exits;
2. already-armed exits;
3. full-position valuation needed by an exit rule;
4. new entry preflight;
5. fixed research follow-ups;
6. optional background valuation.

Reserve most provider capacity for exits whenever positions are open. Admission rate must be derived from observed quote capacity, open-position refresh demand and latency SLOs, not from an arbitrary global “safety” cap. Record queue and provider latencies separately.

## 13. Storage design

Continue one SQLite writer and WAL. Avoid storing every high-frequency observation for the full discovery universe.

- immutable decision-linked MarketFrames;
- compact fixed-window aggregates;
- raw transaction/signature/slot references sufficient for audit;
- exact held-position account events;
- append-only intents/attempts/fills/outcomes;
- mutable projections only when reconstructable from immutable events;
- indexes led by `(version, token/cohort, available_at)`, `(pool, slot)` and due-state fields;
- short transactions; no Agent/network await while a write transaction is held;
- bounded Web queries and precomputed account snapshots.

Storage retention may roll non-decision raw telemetry into fixed aggregates, but never delete registered cohort denominators, failures, orders, fills, writeoffs or the source rows referenced by a decision.

## 14. Web product architecture

The landing page becomes a trading cockpit, not a wall of 12 historical cards.

### Home / Cockpit

Above the fold:

- runtime/DB/WebSocket/collector/quote/execution heartbeats with last real event time;
- dynamic Token-discovery pulse driven by persisted arrivals;
- pending critical exit count and oldest exit latency;
- open positions by `GREEN/WATCH/EXIT_ARMED/DEAD`;
- executable equity versus indicative/unknown valuation;
- recent OrderIntent -> Attempt -> Fill/Failure stream;
- funnel: discovered -> frame-ready -> strategy-admitted -> bought -> exit-armed -> closed/writeoff;
- only mature top strategies; otherwise explicit `LEARNING / UNRANKED`.

### Secondary pages

- `/strategies`: all versions, policy contracts, maturity, exact comparable cohorts and account curves;
- `/positions`: risk-state matrix, full-size executable recovery, route/account freshness and pending exit;
- `/tokens/:id`: launch/flow/route/pool/Agent timeline and all strategy decisions;
- `/execution`: intent/plan/attempt/fill latency and failure semantics;
- `/risk`: pool/vault/mint alerts, stalls, route degradation, writeoffs and no-reentry surfaces;
- `/learning`: gate ablations, rejected counterfactuals, exit-feature diagnostics and promotion lifecycle;
- `/chains`: chain-specific execution/cost/safety maturity;
- `/system`: queue capacity, provider health, SQLite/write latency and collector gaps;
- `/history`: immutable v1–v4 evolution and supersession record.

Every UI poll reads persisted state only. No browser request may call Jupiter/RPC or mutate strategy state. No ranking is shown when valuation is incomplete or the maturity gate is not met.

## 15. BSC and Robinhood Chain

Do not fork the strategy engine. After the generic execution lifecycle works on Solana:

- implement a chain adapter with amount-specific firm BUY/SELL quote, Router transaction simulation, allowance, transfer-tax/blacklist semantics, dynamic gas and L1/L2 fees;
- BSC needs explicit tax/honeypot/MEV failure treatment;
- Robinhood requires exact official Stock Token/RWA exclusion before any Meme cohort and its own Arbitrum-L2 fee accounting;
- register chain-specific strategy/execution/cost versions and keep results separated by chain/venue;
- only after complete round-trip semantics and forward samples may a chain move from research-only to Paper.

## 16. Ordered implementation plan

### P0-A — freeze truth and register v5 architecture

- verify current v4 frontier and open positions;
- create a forward-only v4 entry-stop/supersession frontier; existing positions continue exits;
- add generic immutable strategy definition/registration fields;
- register the 12 v5 complete policies and explicit `paper_role/live_eligibility/research_treatment`;
- correct Web wording so v4 is historical evolution, not independent strategy alpha.

### P0-B — shared decision/execution lifecycle

- add shared candidate/MarketFrame reference, StrategyDecision, OrderIntent, Plan, Attempt, Fill and PositionEvent lineage;
- one quote/preflight may serve many v5 virtual strategy decisions at the same time/amount;
- Paper adapter only; Live locked;
- exact no-route/error/late/interrupted terminals and idempotent restart recovery.

### P0-C — priority exit kernel

- map current held-account alerts and existing deterministic marks into the new exit state machine;
- single exit-first provider scheduler;
- price/provider stall as warning, exact account + economic failure as terminal;
- terminal/no-reentry remains immutable.

### P1-A — PumpSwap flow/MarketFrame decoder

- decode and aggregate strict-as-of trade/vault flow;
- create 1–60 second features and data-quality flags;
- validate against exact account deltas and current provider snapshots without treating provider data as the execution source of truth.

### P1-B — activate independent entries and exit variants

- launch-recall bounded risk buckets first;
- flow-acceleration after decoder evidence is available;
- reawakening only after genuine forward dormant baselines exist;
- Fast/Balanced/Peak policies use the same entry fill within each family.

### P1-C — post-buy investigation case

- shared deterministic evidence package and at most two Agent lanes;
- advisory treatment first, then separately preregister an affecting treatment if coverage/latency/evidence quality is adequate.

### P2 — learning and cockpit

- gate-ablation outcome views, exact paired comparisons, robust metrics and promotion state machine;
- cockpit first, strategy/research/history subpages second;
- no broad cosmetic rewrite before the operational data contract is correct.

### P3 — EVM adapters

- BSC then Robinhood firm execution observation and Paper promotion path;
- Base remains optional research unless user priority changes.

## 17. First release acceptance criteria

The first coherent v5 release is accepted only when:

1. v4 history is unchanged, v4 old positions continue to close, and no post-frontier v4 entry occurs;
2. all 12 v5 policy definitions are immutable, complete and machine-readable;
3. one natural eligible cohort creates one shared quote/preflight and the correct strategy decisions/virtual allocations without duplicate provider work;
4. new positions can produce an exit intent, exact-size Paper quote and fill/no-route/error terminal through the generic lifecycle;
5. critical exit work demonstrably preempts entry/research work;
6. restart is idempotent and cannot duplicate intents, fills or positions;
7. Web truthfully separates v4 history, v5 strategies, executable/indicative/unknown values and Paper/Live state;
8. Live remains locked and no secret, wallet material or transaction payload is exposed.

## 18. Explicit non-claims

- No current strategy is proven profitable or ready for capital scaling.
- More Paper trades alone do not prove alpha.
- A quoted minimum output is not a guaranteed fill.
- Flat price alone is not proof of a rug.
- An Agent’s positive narrative is not proof of authenticity or future return.
- A local-top diagnostic may be useful without ever selling at the exact maximum.
- BSC/Robinhood route availability is not complete execution economics.

The purpose of v5 is to produce enough truthful, diverse, executable forward evidence to discover which complete policies actually make money—and to stop losing policies quickly—without corrupting the data needed to learn that answer.
