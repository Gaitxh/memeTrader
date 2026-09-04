# GXH memeTrader：单主升浪假设、峰值退出与可上市盈利系统研究 V2

- Authority: ChatGPT Lead research / Codex execution contract support
- Date: 2026-09-04 Asia/Tokyo
- Fact cutoff: 2026-09-03T17:53:51.824666Z
- Active cycle: `memetrader-single-wave-v6-market-grade-20260904`
- Scope: Solana first; Paper/Shadow only; Live remains locked
- Supersedes: none. This document extends, but does not rewrite, immutable prior registrations or evidence.

## 0. Executive decision

The user's intuition is directionally valuable but must be stated in tradable terms:

> Many very young meme coins exhibit one dominant attention/liquidity impulse. After a sufficiently persistent drawdown from the **as-of full-position executable-equity high**, the conditional hazard of irreversible collapse often rises sharply. The profitable action is usually not to prove that the coin is permanently dead, but to exit before executable liquidity disappears and retain the option to open a new `REAWAKENING` cohort if a genuinely new wave later appears.

This is an active, falsifiable hypothesis, not a universal fact. Four distinct mistakes must be avoided:

1. Never use future ATH or future route status to label a live exit.
2. Never equate a stale indexer price with a removed pool.
3. Never hold an unarmed loser merely because a profit-trailing rule did not arm.
4. Never count 12 copied strategy accounts as 12 independent profitable market opportunities.

Immediate priority is therefore:

1. Exact all-position RiskKernel and event-driven critical SELL lane.
2. Valid same-BUY-Fill exit comparisons with a common catastrophe envelope.
3. Unique/netted executable PNL and tail truth.
4. MarketFrame and lifecycle features.
5. Broad-entry, risk-sized trading; not narrow defensive filtering.
6. Shared post-buy research with a defined route from observer to bounded sizing/hold influence.
7. Only after the Solana kernel is economically credible: small Live canary, then BSC/other-chain adapters.

## 1. What the first natural Stage-4 evidence says—and does not say

### 1.1 Positive forward signal

The first natural executable-decay v1 exit, cohort 2314, copied source Stage-4 BUY Fill 443. Full-remaining executable recovery reached 41.283448U. After an as-of valuation at 33.953885U crossed the frozen 15% drawdown from executable high, the next Jupiter minimum-output Paper Fill was 28.263148U. On a 20U stake, challenger realized +8.263148U.

This validates several engineering properties:

- Same real source BUY Fill can support an exit counterfactual without inventing another entry.
- Full-position executable recovery is materially better than display price for triggering exits.
- A high-water decay exit can monetize part of a fast impulse.
- The OrderIntent -> next quote -> Fill lineage works naturally.

It does **not** establish strategy profitability, because:

- the paired control was not terminal at the cutoff;
- one winner is not an independent distribution;
- simulated quote Fill remains execution level L0, not confirmed transaction execution;
- copied accounts must not multiply the economic sample or headline PNL.

### 1.2 Natural invalidation of v1 as a causal comparator

Cohort 2313 shows the opposite branch. Source Stage-4 control closed on its hard stop for -8.400716U. Challenger never reached the +40% arm, peaked around 21.114082U executable recovery, later fell to 10.255032U, and remained open. This is not a legitimate isolated comparison of peak exits: control and treatment do not share the same non-alpha safety envelope.

Required consequence:

- freeze v1 new enrollment, preserve its history;
- create future-only v2;
- share hard stop, exact RED/DEAD, max hold and terminal/no-route behavior;
- let only the profit-harvest rule differ;
- count a pair only when both arms are terminal or share an explicit terminal/writeoff.

## 2. A more accurate lifecycle model than “one wave and dead”

A listing-grade system should represent each exact Token/pool cohort as a state machine. State is inferred only from information available at that time.

### 2.1 Lifecycle states

1. `DISCOVERY`
   - first exact surface, early trades, high uncertainty;
   - broad recall is acceptable, but size is small and sellability coverage is mandatory.

2. `IMPULSE`
   - fast positive executable-equity slope;
   - quote reserve is not collapsing; unique buyers/flow quality expand;
   - optional add-on may be permitted after full-size sellability heartbeat.

3. `EXPANSION`
   - repeated higher executable highs, stable/improving route depth, healthy reserve flow;
   - trailing may be looser because premature exit cost is high.

4. `DISTRIBUTION`
   - price/executable high stalls while sell flow, concentration or impact rises;
   - repeated failed new-high attempts and shorter rebound half-life;
   - tighten profit protection or take partial principal.

5. `BREAKDOWN`
   - persistent executable drawdown with negative flow/reserve confirmation;
   - exit is favored even if permanent death is not proven.

6. `RED`
   - event-driven one-sided quote-reserve drain, full-position recovery collapse or other high-confidence catastrophe;
   - preempt ordinary work and sell the full remaining position.

7. `DEAD`
   - exact market/account terminal, exact identity failure, or exhausted full-position sellability under frozen semantics;
   - no rearm on that exact surface.

8. `REAWAKENING`
   - a later, independently qualified wave after a prior exit;
   - create a new cohort, new cost basis and new evidence frontier;
   - never rewrite the original exit as a mistake simply because a later wave existed.

### 2.2 Why this is economically better

The system does not need to predict the final historical top. It needs to decide whether the expected value of continuing to hold is lower than:

- the executable cash available now;
- plus the option value of buying a genuinely renewed wave later;
- minus exit and possible reentry costs.

This converts an impossible question—“is this the permanent top?”—into a measurable competing-risk problem:

- reclaim/exceed current executable high first;
- or hit a catastrophic recovery floor / route terminal first;
- within 5s, 15s, 60s, 5m, 15m and 60m horizons.

## 3. The tradable state variable must be executable equity, not screen price

For a position with realized cash `C_t` and remaining raw amount `q_t`, define:

- `X_t(q_t)`: minimum executable quote-currency recovery for the full remaining amount at time t;
- `E_t = C_t + X_t(q_t)`: total executable equity;
- `H_t = max(E_s for s <= t)`: as-of executable-equity high;
- `D_t = 1 - E_t / H_t`: executable drawdown;
- `V_t`: drawdown velocity;
- `A_t`: drawdown acceleration.

Important implementation rules:

- A changing remaining amount after partial exits means raw token price high is not comparable. High-water tracking should use total executable equity, including realized cash.
- A quote is valid only for the exact full remaining raw amount and exact surface identity.
- Display/indexer price may be used as low-cost context, never as the decisive cash-recovery truth.
- Missing/stale executable truth is its own risk/coverage state, not zero PNL and not HEALTHY.

## 4. MarketFrame V1: the minimum event-time dataset needed for profitable exits

Each exact Token/pool position should consume a common, append-only MarketFrame. Strategy arms read the same frame; they must not each fetch and mutate their own version of market truth.

### 4.1 Exact surface and execution fields

- event time, receive time, slot/block, source and freshness;
- exact Token/mint, pool, base vault, quote vault, LP mint and program owners;
- remaining raw amount;
- full-position executable output, minimum output, route identity and price impact;
- quote/order/execute result and latency components;
- explicit missing/stale/ambiguous state.

### 4.2 Reserve and flow fields

- quote/base raw reserve;
- ratio versus entry baseline and rolling high;
- 1s/3s/10s/30s slope and acceleration;
- signed quote-out/base-in flow;
- trade buy/sell amount and count imbalance;
- unique buyer/seller approximation;
- large-trade share and burstiness;
- marginal impact for several probe sizes when budget allows.

The main risk pattern already seen locally is not only LP removal. Sell flow can drain the quote vault while base tokens accumulate, destroying full-position recovery within seconds. Therefore `RED` and `DEAD` must remain different states.

### 4.3 Trend/distribution fields

- executable-equity return from entry;
- executable high-water drawdown, velocity and acceleration;
- time since high;
- number and spacing of failed new-high attempts;
- rebound amplitude and rebound half-life;
- volume/unique-buyer divergence from executable price;
- reserve/recovery divergence;
- age since exact pool creation/migration;
- holding-concentration changes when available as-of.

### 4.4 Quality and manipulation fields

- wallet concentration and creator/deployer holdings;
- deployer prior token/pool outcomes as-of;
- repeated same-wallet round trips or likely wash clusters;
- mint/freeze/transfer restrictions and token program truth;
- route disagreement and surface mismatch;
- source-link ambiguity and clone/fanout count;
- data-gap duration and provider disagreement.

## 5. All-position RiskKernel: profit protection before alpha refinement

The highest expected-value defect is not a missing narrative classifier. It is that a 20-second reserve/recovery collapse can outrun the current runtime schedule.

### 5.1 Coverage contract

Every open position, including Stages 1–12 and every future challenger, must be linked immediately after BUY Fill to an exact risk surface. The status is one of:

- `COVERED_HEALTHY`
- `COVERED_ORANGE`
- `COVERED_RED`
- `COVERED_DEAD`
- `COVERAGE_GAP`

There is no implicit HEALTHY default.

### 5.2 Subscription architecture

Current whole-WebSocket restart when target fingerprint changes is unsuitable for all-position monitoring. Required design:

- deduplicate by account/pubkey;
- subscribe once, fan out to linked positions;
- incrementally add/remove, or use bounded stable shards;
- retain an HTTP/secondary-source fallback during reconnect;
- record p50/p95/p99 gap duration and event-to-decision latency;
- resolve actual account owner, including Token-2022, rather than hardcoding legacy Tokenkeg.

### 5.3 Risk severity

`ORANGE` should be sensitive, because the cost is mainly reserved preflight and no add-on:

- early one-sided quote reserve deterioration;
- executable recovery decay faster than ordinary price volatility;
- widening full-size impact;
- feed/route uncertainty during a negative flow burst.

`RED` should trigger a full-position SELL intent through the critical lane:

- persistent one-sided quote-out/base-in reserve movement;
- steep full-position executable-recovery collapse;
- large sell burst plus reserve/recovery confirmation;
- exact control/authority hazard that still leaves a route available.

`DEAD` is exact terminal:

- exact account/pool missing or invalid under the frozen identity contract;
- exact market surface terminal;
- or exhausted full-position sellability after explicit retry/writeoff semantics.

Thresholds must be versioned and forward-only. Initial thresholds should favor early escape and can be challenged by later versions; no backfilling of favorable exits.

### 5.4 Critical execution lane

Priority must be explicit:

1. RED/DEAD full-position SELL;
2. ORANGE full-position preflight;
3. existing pending risk SELL;
4. ordinary strategy SELL;
5. BUY;
6. valuation/research/hydration/Web.

A dedicated single-flight or reserved-capacity lane prevents the normal three-per-five-second background quota from consuming all emergency capacity. Identical same-cohort intents may share a fetched quote, but each arm retains lineage.

## 6. Exit Lab: test several profit mechanisms without contaminating entry

Broad entry should not be tightened merely to produce cleaner-looking statistics. Keep trade recall, and compare exits from the same source BUY Fill.

### 6.1 Mandatory common envelope

All paired challengers share:

- same BUY Fill and full raw amount;
- same event-time MarketFrame availability;
- same hard stop;
- same RED/DEAD action;
- same max hold;
- same no-route/writeoff semantics;
- same execution kernel and priority class, except where the experiment explicitly studies execution priority.

Only the alpha exit component differs.

### 6.2 Candidate exit families

Keep each family in a separate future-only registration. Do not launch all variants simultaneously before the RiskKernel is stable.

A. `EXEC_DECAY_FULL`
- arm after +40% full-position executable recovery;
- full exit at 15% drawdown from executable-equity high;
- current v2 baseline treatment.

B. `PRINCIPAL_THEN_TRAIL`
- recover 25–50% or original principal at a frozen executable threshold;
- track total executable equity on the remainder;
- trail the remainder with a wider threshold;
- useful if multi-leg expansion exists, but must include realized cash in high-water accounting.

C. `REGIME_ADAPTIVE_TRAIL`
- wide trailing in EXPANSION;
- tighten after DISTRIBUTION evidence;
- no future peak label; only as-of state transitions.

D. `FAILED_HIGH_TIME_DECAY`
- exit after a frozen number/duration of failed executable-high attempts;
- useful where volatility alone would trigger a fixed trailing stop too early.

E. `FLOW_BREAKDOWN`
- exit on reserve/recovery/flow change point even before a large headline price drawdown;
- distinct from exact catastrophe RED only by confidence/severity.

F. `EXIT_AND_REAWAKEN`
- exit at breakdown;
- create a new observation-only reawakening watch;
- new BUY is permitted only on a new cohort with renewed executable depth and fresh demand evidence.

### 6.3 Evaluation metrics

For each exact independent cohort:

- net executable PNL;
- realized and unresolved exposure;
- max adverse executable excursion;
- captured fraction of as-of available executable run-up;
- giveback from executable high to Fill;
- trigger-to-intent, intent-to-quote, quote-to-Fill latency;
- time in capital and return per capital-hour;
- route/no-route/writeoff/tail outcomes;
- remove-best-1 and remove-best-3 PNL;
- median and lower-tail results;
- pair-complete count and right-censored count.

No strategy is promoted on win rate or gross display-price return alone.

## 7. How to test the “single dominant wave” hypothesis correctly

### 7.1 Prospective event definition

For one exact cohort, define the first qualifying event after:

- a prior as-of executable-equity rise of at least a frozen amount;
- followed by drawdown threshold `d` persisting for `p` seconds or frames;
- with exact observation coverage.

Freeze multiple coarse cells before observing future outcomes, for example:

- rise: 25%, 40%, 75%, 150%;
- drawdown: 10%, 15%, 20%, 30%;
- persistence: immediate, 3s, 10s, 30s;
- horizons: 15s, 60s, 5m, 15m, 60m, 240m.

This is a descriptive grid, not a large optimizer. Select operational rules in a later temporal window.

### 7.2 Competing outcomes

Track which happens first:

- rehit prior executable high;
- exceed it by a frozen margin;
- hit a catastrophic executable recovery floor;
- exact RED/DEAD;
- horizon censoring.

Do not treat an observation ending before the horizon as “no recovery.” Use explicit right-censoring and, when sample size supports it, survival/competing-risk estimates.

### 7.3 De-duplication

- one event per exact Token/pool cohort until a frozen refractory period;
- clone/fanout tokens remain separate surfaces but grouped for robustness analysis;
- 12 strategy accounts never multiply the event count;
- a later genuine wave is a new REAWAKENING cohort, not a second event retroactively attached to the original trade.

### 7.4 Stratification that matters

- pool age and migration phase;
- quote reserve and full-size impact;
- prior run-up magnitude and speed;
- buy/sell/unique-wallet flow quality;
- reserve/recovery divergence;
- holder/deployer concentration;
- exact venue/program;
- social/narrative evidence, when available strictly as-of;
- data coverage and feed latency.

The goal is not one universal drawdown number. It is to identify where a tight exit dominates and where a looser/partial policy preserves multi-leg winners.

## 8. Keep trade count high through sizing and staging, not by ignoring tail risk

The user's goal is profit, not a pristine classifier with almost no trades. The right compromise is broad bounded admission plus adaptive capital.

### 8.1 Seed/add architecture

A future experiment can compare:

- small seed on broad valid on-chain impulse;
- immediate full-size sellability heartbeat;
- add only when exact coverage is healthy and IMPULSE/EXPANSION evidence persists;
- never add in ORANGE; always exit in RED/DEAD.

This preserves opportunity count while reducing the amount exposed before sellability and regime are known.

### 8.2 Liquidity-aware sizing

Size from executable curves, not nominal liquidity:

- request/replay several probe sizes when capacity permits;
- freeze maximum acceptable full-size impact and maximum risk-at-writeoff;
- cap total real economic exposure per exact cohort across all strategy representations;
- 12 research arms are counterfactual accounts, not 12x deployable capital.

### 8.3 Portfolio controls

- per-cohort cap;
- concurrent exposure cap;
- daily realized + executable drawdown cap;
- venue/provider concentration cap;
- correlated clone/narrative exposure cap;
- capital reservation for emergency exits;
- no new BUY during degraded execution/risk coverage.

These controls should reduce size or pause new exposure, not fabricate exits or erase losses.

## 9. Post-buy research: useful, shared and eventually actionable

One shared Token/cohort case is correct. Twelve agents should not repeat the same investigation.

### 9.1 Parallel specialist modules

Within a bounded deadline, dispatch structured modules:

1. exact contract/pool/authority truth;
2. deployer and related-wallet history;
3. holder/concentration/cluster change;
4. narrative/source/catalyst identity and ambiguity;
5. market microstructure/manipulation signs;
6. contradiction/red-team synthesis.

Each output carries:

- `as_of` and source timestamps;
- retrieval time and evidence hash;
- exact identity/surface;
- positive, negative, ambiguous and missing evidence separately;
- no free-text direct trading command.

### 9.2 Trading authority ladder

Current observer-only mode should not be permanent. Pre-register promotion steps:

- Level A: observer, no effect;
- Level B: affects only optional add-on and monitoring priority;
- Level C: bounded size multiplier / trailing-width feature after temporal out-of-sample uplift;
- Level D: broader decision eligibility only after live-canary calibration.

Agent output must never weaken an exact RED/DEAD exit. It may accelerate caution, cancel an add-on or tighten a non-catastrophe hold policy after promotion.

### 9.3 Promotion evidence

Use unique cohorts and temporal splits. Promote only if the research feature improves at least one economic objective without worsening hidden tail:

- net executable PNL;
- downside/tail/writeoff rate;
- capital-hour efficiency;
- remove-top-winner robustness;
- calibration of its confidence/coverage.

No endless shadow period is required. Once accounting, coverage and a minimally informative forward cohort exist, promote the smallest bounded influence and keep a concurrent control.

## 10. Profit accounting that cannot be fooled by copied accounts

Maintain three separate ledgers/headlines:

1. `strategy_counterfactual_pnl`
   - every arm, useful for policy comparison;
   - explicitly not deployable system profit.

2. `portfolio_paper_pnl`
   - unique/netted exact cohort exposure;
   - one economic stake unless a real portfolio allocator explicitly funds more;
   - all simulated costs and unresolved/writeoff truth included.

3. `live_confirmed_pnl`
   - confirmed on-chain execution, fees, priority/tip, failed transactions and inventory;
   - absent until Live canary is explicitly unlocked.

Required headline robustness:

- unique-cohort total, median and distribution;
- Top1/Top3 contribution;
- remove-best-1/remove-best-3;
- tail loss, no-route, writeoff and unresolved exposure;
- realized versus executable remaining equity;
- capital-hour return;
- execution level L0–L4.

## 11. From Paper to a market/listing-grade product

### 11.1 Execution truth ladder

- L0: quote/min-output simulation only;
- L1: built unsigned/signed transaction simulation;
- L2: submitted canary, not yet economically confirmed;
- L3: confirmed transaction with exact balance reconciliation;
- L4: production accounting with retries, failures, fees, tips and inventory reconciliation.

Current Paper Fill must remain labeled L0.

### 11.2 Release sequence

R0 — Forward Paper kernel
- exact data lineage, risk coverage, unique PNL, paired exits.

R1 — Shadow execution canary
- build/simulate transaction, no broadcast;
- measure blockhash expiry, account locks, slippage and compute/priority requirements.

R2 — Tiny Live canary
- one venue/chain, fixed tiny risk, hard daily loss and inventory caps;
- Live and Paper share OrderIntent/risk/accounting path;
- every deviation is explicit.

R3 — Limited beta
- stable operational SLOs, alerting, recovery and evidence export;
- user-facing disclosures and execution-level labels.

R4 — Commercial production
- key custody boundary, tenant isolation, permissions, audit, incident response, compliance review, backups/restore drills and billing/product controls.

Do not demand an enormous sample before a tiny canary; demand sound safety, accounting and non-fragile forward evidence. Conversely, do not call L0 quote simulation live-ready.

### 11.3 Operational engineering

- event loop and risk-lane latency SLOs;
- provider health and circuit breakers;
- append-only audit trail and deterministic replay;
- database/WAL capacity, backup and restore verification;
- SQLite version remediation where current official release notes identify WAL-reset risk;
- no secret leakage in logs/UI/research artifacts;
- restart recovery without duplicate orders;
- explicit stale/missing data states;
- terminal and unresolved inventory reconciliation.

## 12. Multi-chain sequencing

Solana remains the proof surface. Adding chains before the common kernel is credible would multiply bugs and obscure economics.

After Solana P0/P1 acceptance, implement chain adapters behind the same contracts:

- discovery/hydration adapter;
- exact market surface and account monitor;
- full-position route/quote adapter;
- OrderIntent -> execution -> reconciliation adapter;
- chain-specific token restrictions/authority/honeypot semantics;
- common MarketFrame, lifecycle, RiskKernel and PNL ledger.

BSC/EVM requires additional treatment of taxes, approvals, blacklist/transfer restrictions, proxy/owner privileges and router path truth. Any future Robinhood-chain work waits for official, stable execution/liquidity interfaces and exact asset-transfer semantics; no roadmap claim substitutes for a functioning adapter.

## 13. Concrete execution queue for Codex

### P0 now

1. Retire Stage-4 executable-decay v1 admissions immutably.
2. Register v2 same-BUY-Fill challenger with common safety envelope.
3. Register all-position exact RiskKernel version.
4. Fix target coverage, Token-2022 owner truth and append-only reserve/recovery windows.
5. Add v5/v6 event-driven critical SELL lane with reserved capacity.
6. Incremental/sharded subscriptions and gap telemetry.
7. Unique/netted PNL headline and unresolved-pair truth.

### P1 after P0 health

1. Common MarketFrame V1.
2. Prospective single-wave/recovery competing-risk ledger.
3. `PRINCIPAL_THEN_TRAIL` and one regime-adaptive challenger, sequentially.
4. Exit-and-REAWAKENING observer.
5. Seed/add sizing experiment using the same broad admission stream.
6. Execution L1 transaction build/simulation lane.

### P2 after forward economic evidence

1. Promote useful research features to bounded add-on/size/hold influence.
2. Tiny Live canary readiness review and canary.
3. Portfolio allocator instead of duplicated funded arms.
4. BSC adapter only after Solana accounting/risk/execution contracts pass.
5. Productization, permissions, incident response and commercial UX.

## 14. Stop/promotion rules

### Stop or replace a strategy version when

- it lacks a common safety envelope versus its comparator;
- it can remain open solely because its profit arm never triggered;
- its positive total depends on one copied underlying winner;
- its trigger is based on display price while full-position recovery contradicts it;
- it cannot distinguish missing data from healthy state;
- its emergency action waits behind ordinary BUY/research work;
- its results cannot be replayed from immutable event-time evidence.

### Promote a version when

- registration and no-backfill contract pass;
- all positions have explicit risk coverage or visible coverage-gap state;
- pair outcomes are terminal-comparable;
- unique-cohort net executable economics are positive and not solely Top1-dependent across a temporal forward cohort;
- tail/no-route/writeoff behavior is bounded and explicit;
- execution/accounting level is labeled honestly;
- the smallest next deployment step has a rollback/kill boundary.

## 15. External evidence classes to maintain in the project source ledger

Codex/ChatGPT should keep retrieved snapshots or exact citations for:

- official Solana RPC WebSocket/account subscription and transaction confirmation semantics;
- official Jupiter order/build/execute and quote semantics;
- official Pump/PumpSwap and Raydium pool/program/account semantics;
- official token-program and Token-2022 account-owner/layout semantics;
- official SQLite release notes for WAL/reset correctness affecting the deployed version;
- peer-reviewed/working-paper evidence on crypto pump-and-dump, rug pulls, meme-token lifecycle and manipulation;
- mature open-source streaming/execution patterns used only as implementation references, never as profitability evidence.

External evidence informs architecture. All claims of GXH strategy profit, latency and risk performance must come from its own immutable forward ledger.

## 16. Final judgment on the user's hypothesis

The strongest defensible answer is:

- **Yes, the one-dominant-wave pattern is common enough to be a high-priority exit hypothesis in this project.** Local forward/historical diagnostics already suggest that persistent drawdown after a meaningful run-up often has a low near-term probability of reclaiming the prior high, especially with reserve/recovery deterioration.
- **No, every drawdown does not mean permanent death.** Some coins form multi-leg trends or awaken again after a new catalyst.
- **The profitable system should exit breakdown early and permit a new reawakening trade, rather than hold through collapse in hope of proving continuity.**
- **The trigger must combine executable-equity high-water decay, persistence, flow/reserve state and route truth.** A single display-price percentage is insufficient.
- **Risk coverage and execution latency dominate additional entry cleverness right now.** A perfect signal cannot monetize if quote reserve disappears before the runtime reaches SELL.

This is the current highest-value route toward a system that trades often enough to learn, protects capital during seconds-scale collapse, captures fast profitable waves, and can later support honest small-scale Live deployment and commercial release.
