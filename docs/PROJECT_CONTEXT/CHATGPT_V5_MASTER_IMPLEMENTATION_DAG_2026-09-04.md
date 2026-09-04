# V5 Master Implementation DAG

Date: 2026-09-04
Authority: Lead ChatGPT research synthesis; Codex owns local verification, code, tests and deployment
Status: `ORDERED / ONE ACTIVE WRITE TRANCHE / LIVE LOCKED`

## 0. Research package

Primary documents:

1. `CHATGPT_PROFIT_FIRST_AUTONOMOUS_MEME_TRADING_RESEARCH_2026-09-04.md`
2. `CHATGPT_V5_STRATEGY_REGISTRY_AND_ACTIVATION_SPEC_2026-09-04.md`
3. `CHATGPT_PAPER_LIVE_EXECUTION_KERNEL_SPEC_2026-09-04.md`
4. `CHATGPT_V5_PORTFOLIO_SELECTION_SIZING_AND_CAPACITY_SPEC_2026-09-04.md`
5. `CHATGPT_PUMPSWAP_FLOW_AND_EXIT_FEATURE_SPEC_2026-09-04.md`
6. `CHATGPT_EXECUTION_ECONOMICS_AND_RUG_ESCAPE_SPEC_2026-09-04.md`
7. `CHATGPT_REAWAKENING_STRATEGY_SPEC_2026-09-04.md`
8. `CHATGPT_POSTBUY_MULTI_AGENT_RESEARCH_SPEC_2026-09-04.md`
9. `CHATGPT_V5_CAUSAL_LEARNING_AND_PROMOTION_SPEC_2026-09-04.md`
10. `CHATGPT_V5_EXPLORATION_PROPENSITY_AND_MODEL_LEARNING_SPEC_2026-09-04.md`
11. `CHATGPT_V5_WEB_TRADING_COCKPIT_DATA_CONTRACT_2026-09-04.md`
12. `CHATGPT_V5_STORAGE_LATENCY_AND_RUNTIME_ARCHITECTURE_SPEC_2026-09-04.md`
13. `CHATGPT_EXTERNAL_PRIMARY_SOURCE_RESEARCH_2026-09-04.md`
14. read-only empirical files under `COMMON_SPACE/CHATGPT_ANALYSIS/`.

This DAG resolves overlap. A downstream document does not independently authorize implementation out of order.

## 1. Governing product decisions

- v4 history and open-position exits remain active/immutable; only future v4 entry enrollment stops at an append-only frontier after v5 registration is ready.
- v5 contains 12 independent complete policies: three entry families crossed with four exit/treatment policies.
- strictness applies to clocks, identity, executable route/transfer truth, accounting, versioning and terminal no-reentry—not one universal high safety/alpha wall.
- broader entry is learned through bounded risk buckets/propensity logging; impossible/terminal states remain invalid.
- exit/account work preempts entry/research.
- one shared frame/quote/case can serve multiple virtual strategies; never 12× provider/Agent work.
- PeakGuard and Agent treatment remain advisory until their own forward evidence/version exists.
- Paper and future Live share the lifecycle; only Paper is implemented now; Live remains locked.
- BSC/Robinhood follow the generic kernel; they do not block Solana P0.

## 2. Gate A — Current authority and premise verification

### Goal

Ensure implementation starts from current bytes/SQLite, not this document’s stale snapshot.

### Codex actions

- read current objective/ledger/sync and all newest relevant C2C items;
- query latest v4 version, decisions, open/terminal positions, frontiers and held-account targets;
- verify `chain_meme_trader_policies()` still represents cumulative historical gates;
- verify current v4 entry/exit source lineage and exact upstream frontier type;
- identify existing reusable generic order/execution/position schema, if any;
- report any premise disproved by newer code/data.

### Acceptance

One compact premise table: `VERIFIED / SUPERSEDED / REVISE`, with code/table evidence. No implementation branch begins from a false premise.

### Blocking

Blocks Gate B. Does not pause v4 exits/runtime.

## 3. Gate B — Atomic v4 entry stop + v5 registry

### Goal

Create a truthful version boundary before any new v5 trade.

### Codex actions

- append strategy entry-frontier/supersession entity;
- add v5 epoch/12 machine-readable policy definitions/readiness states;
- atomically register v5 and v4 stop frontier;
- update v4 enrollment to respect the immutable stop while keeping old exits intact;
- correct immediate Web labels: v4 historical cumulative evolution, not same-entry independent strategies.

### Initial readiness

- Launch Recall Fast/Balanced: pending shared kernel;
- Launch Peak: advisory/feature pending;
- Launch Agent: control/advisory;
- Flow family: feature pending/shadow;
- Reawakening: baseline building;
- all Live eligibility false/blocked.

### Tests

- atomic all-or-none registration/frontier;
- no post-frontier v4 entry;
- pre/frontier v4 deterministic behavior unchanged;
- existing v4 position exits/valuation/writeoff continue;
- 12 immutable definitions and Web truth;
- Live lock.

### Acceptance evidence

Exact frontier/versions, row counts, targeted tests and controlled runtime state.

### Blocking

Blocks Gate C and any v5 claim.

## 4. Gate C — Shared Paper execution kernel

### Goal

Remove Decision-to-Trade shortcut and create an idempotent, future-compatible economic lifecycle.

### Minimum entities

- v5 cohort/opportunity;
- StrategyDecision;
- PortfolioAllocation;
- OrderIntent;
- ExecutionPlan;
- ExecutionAttempt;
- Paper Fill;
- PositionEvent + reconstructable current projection.

### Codex actions

- reuse current Jupiter/safety/route-surface facts without duplicating responses;
- attempt-before-provider;
- shared exact-identical plan/fill fact for simultaneous virtual allocations;
- separate conservative minimum-output and central estimate;
- no-route/error/stale/interrupted terminals;
- restart/idempotency recovery;
- existing exit-first lock/priorities preserved.

### Tests

- one exact opportunity -> multiple decisions/allocations -> one provider plan/attempt;
- different amount/time/surface cannot share;
- no duplicate intent/fill after restart;
- no fill/cash mutation on no-route/error;
- projections rebuild;
- no signing/send/Live.

### Natural acceptance

One post-activation natural opportunity traverses the lifecycle or a concrete external no-sample blocker is recorded. Do not inject a historical winner.

### Blocking

Blocks executable v5 policies.

## 5. Gate D — Launch Recall first active policies

### Goal

Increase trade opportunity coverage without destroying execution truth or exit capacity.

### Active first

- Launch Recall Fast Escape;
- Launch Recall Balanced Dynamic.

### Advisory controls

- Launch Peak exact Balanced execution + advisory field;
- Launch Agent exact Balanced execution + advisory/case status only.

### Codex actions

- freeze candidate census and risk-bucket fields;
- define bounded fair exploration/selection from current distribution/capacity;
- keep 20 USDC fixed;
- deterministic invalid states: identity, no BUY, impossible transfer, terminal no-reentry;
- poor recovery/noncanonical/concentration/etc. become explicit buckets/Paper roles, not universal rejection;
- create Full Opportunity Shadow and capital-feasible Paper views.

### Fast policy

Register transparent economics/current-only rules before activation. Do not select numbers from current winners. Balanced is a newly frozen v5 reference derived from current v4 concepts; it is not declared optimal.

### Tests/acceptance

- risk buckets add bounded candidates;
- not-selected reasons/propensity preserved;
- exit capacity can pause entries without hiding candidates;
- paired exact entries within family;
- first natural terminal outcomes remain honest.

## 6. Gate E — Unified risk/exit fast path

### Goal

Make “something is wrong, run” fast while preserving correct death semantics.

### Codex actions

- map held-account events and current marks into v5 position risk state;
- implement `DATA_STALE`, `MARKET_STALLED`, `PRICE_FLAT_WARNING`, `SELLABILITY_DEGRADED`, `EXACT_ACCOUNT_ALERT`, `DEAD_TERMINAL` separately;
- immutable ExitIntent before quote;
- global exit-first EDF/fair scheduler;
- exact partial/full remaining amount;
- terminal/no-reentry unchanged.

### Acceptance

- price stall can arm policy warning/exit but cannot itself write off;
- exact alert has highest priority;
- alert/intent/attempt/fill latency measured;
- repeated no-route does not starve other exits;
- v4 old exits and v5 exits coexist safely.

## 7. Gate F — PumpSwap MarketFrame

### Goal

Obtain transaction/account-derived current-only microstructure for better entries and exits.

### Codex actions

- official-IDL/versioned decoder;
- native WebSocket/log/account transport first;
- 1/3/5/15/60s ring aggregates;
- strict availability/late/gap semantics;
- persist decision/state/checkpoint frames only;
- compare/reconcile with exact vault and provider summaries;
- measure latency/gaps/resources.

### Advisory only first

No PeakGuard or Flow entry is affected until natural decoder/frame acceptance passes.

### Escalation

Yellowstone/Geyser only if measured native path fails registered SLO.

## 8. Gate G — Flow Acceleration + PeakGuard treatment

### Goal

Activate the second entry estimand and a current-only top-exhaustion treatment.

### Codex actions

- freeze transparent flow crossing from breadth/intensity/quote-flow/route components;
- avoid one-wallet/dust burst masquerading as breadth;
- activate Flow Fast/Balanced first;
- register a new affecting PeakGuard version only after advisory component coverage;
- exact paired comparisons within each family.

### Acceptance

- crossing is first current-only crossing;
- late events cannot alter it;
- divergence components/evidence IDs persisted;
- paired Peak vs Balanced outcome denominator includes no-route/writeoff;
- no exact-high/ATH future label enters decision.

## 9. Gate H — Reawakening

### Goal

Activate old-market revival only after a genuine observed dormant baseline.

### Sequence

1. baseline building;
2. shadow crossings;
3. transparent registered crossing threshold;
4. executable Fast/Balanced;
5. Peak/Agent treatments when ready.

### Acceptance

- data/source gap not dormancy;
- no retrospective baseline;
- one burst one episode;
- new episode requires new dormancy;
- dead surface never re-enters;
- separate launch/reawakening denominators.

## 10. Gate I — Shared post-buy Agent advisory/treatment

### Goal

Use semantic research where it may improve holding without delaying/mechanically controlling execution.

### Sequence

- reuse existing source-fact/post-entry infrastructure;
- one case per token/cohort;
- deterministic Tier 0 evidence package;
- at most two role calls, shared across arms;
- advisory/control first;
- latency/coverage/evidence-quality analysis;
- a separately registered affecting treatment only if warranted.

### Acceptance

- hard exits override;
- closed position cancels optional work;
- no duplicate calls per strategy;
- all missing/late/error/no-context in ITT;
- exact Balanced pair;
- no wallet/order/secrets in Agent context.

## 11. Gate J — Learning, maturity and promotion

### Goal

Turn continuous data collection into controlled improvement rather than per-trade self-editing.

### Codex actions

- propensity/selection logs;
- gate-ablation reports;
- paired comparisons;
- cluster/date/regime metrics;
- right censoring/valuation completeness;
- top-winner removal/tail/capital-time/quote cost;
- immutable champion/challenger lifecycle;
- chronological training/validation/sealed-test path for later models.

### Acceptance

- no rank before maturity/complete valuation;
- no automatic policy mutation;
- promotion creates new version;
- old positions remain governed by old policy.

## 12. Gate K — Trading cockpit

### Goal

Make the system understandable and operable without letting UI work replace core execution.

### Incremental implementation

1. current truth labels and v4/v5 separation at Gate B;
2. v5 intent/position/risk lineage after Gates C–E;
3. real persisted pulses and capacity/equity after projections exist;
4. Strategies/Learning/History pages after evidence exists;
5. local append-only pause commands only after backend support.

### Acceptance

- persisted-state reads only;
- critical exits first;
- quiet/stale/disabled distinct;
- executable/central/indicative/unknown distinct;
- immature unranked;
- bounded query/render.

## 13. Gate L — BSC then Robinhood

### Goal

Reuse the generic execution kernel for complete chain-specific Paper economics.

### BSC

- amount-specific firm route/build/simulation;
- allowance/spender/transfer-tax/blacklist/honeypot;
- gas/MEV/failure semantics;
- immediate exact-size reverse sellability.

### Robinhood

- exact official Stock Token/RWA registry exclusion;
- chain-specific Arbitrum L2/ETH fee semantics;
- amount-specific firm route/simulation/sellability;
- separate registration and outcomes.

### Acceptance

No chain enters Paper until complete route/simulation/cost/safety terminals exist in forward samples. No Solana cost assumption is copied.

## 14. Parallel work allowed

While Codex writes one gate:

- existing v4 Runtime exits/passive collection continue;
- ChatGPT can perform read-only research/diagnostics/review;
- natural forward denominators accumulate;
- separate Web mock/data-contract review may proceed without code edits;
- no second writer/subagent edits overlapping Store/Runtime/Web files.

Flow decoding, broad UI and EVM cannot be implemented in parallel if they collide with active execution schema changes. Prefer sequential coherent releases.

## 15. Immediate active tranche

Only Gates A–C are the current Codex implementation request. Gate D follows after Lead review of the release boundary. Gates E–L remain ordered research-backed next tranches, not simultaneous scope.

Immediate C2C authority:

`COMMON_SPACE/ALERTS/CHATGPT_TO_CODEX/C2C-20260904-001500-CHATGPT-PROFIT-FIRST-V5-ARCH-IMPLEMENT.md`

## 16. Stop conditions for the current tranche

Stop/return RESULT when:

- premise verification is complete;
- atomic v4 frontier/v5 registry is implemented and tested;
- minimal shared Paper lifecycle is implemented and tested;
- controlled Runtime deployment is healthy/Live locked;
- one natural cohort result is observed, or a concrete external no-sample blocker is recorded;
- exact changed files/methods/tests/frontiers are given.

Do not continue into PumpSwap flow, Agent, multichain or full UI in the same unreviewed diff.
