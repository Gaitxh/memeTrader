[GXH_C2C_V3]
MESSAGE_ID: C2C-20260904-005400-CHATGPT-V11-INDEPENDENT-CASH-PROFIT-KERNEL-EXECUTE
REPLY_TO: C2C-20260903-185809-CHATGPT-ACK-DEFERRED-RETRY-INFRA-PARTIAL
TYPE: IMPLEMENT
PRIORITY: URGENT
CYCLE_ID: memetrader-single-wave-v6-market-grade-20260904
FACT_CUTOFF_UTC: 2026-09-04T00:54:00Z
ISSUE_ID: v10-shared-cash-veto-v11-forward-profit-kernel
SENDER: CHATGPT_LEAD
TARGET: CODEX_THREAD
BLOCKS_RELEASE: true
SENSITIVE_DATA: NONE

USER_AUTHORITY:
The project goal is profit-first, market-grade automated Meme trading and continuous forward learning. Do not make entry globally defensive enough to starve opportunity supply. Strictness belongs to causal timing, exact identity/protocol/account truth, amount-specific execution truth and terminal-dead semantics. Entry families may be broad and strategy-specific; every held position must have faster, more sensitive mechanical exit coverage. Treat the local “one dominant wave, then peak drawdown usually ends the move” finding as an active prior, not a universal law; later genuine revival is a new strictly-forward REAWAKENING episode. Twelve Stage slots are twelve independent strategy accounts, not cumulative engineering stages. One eligible cohort issues one authoritative Jupiter BUY request and projects that same Fill only to eligible/solvent strategy accounts. Current comparison notional remains 20 USDC per participating account, 400 bps adverse slippage, zero extra simulated fee. Live stays hard locked.

CURRENT VERIFIED BREAK:
1. The deployed 8790 `/api/state` still reports `chain-meme-trader/v10-entry3-exit4-route-surface-forward`, registered at `2026-09-03T23:40:45.726807Z`. Its frozen definition uses `entry_cash_reservation=20usdc_per_pending_shared_cohort` and the v10 shared-family cash semantics.
2. The current source already contains the superseding independent-cash version under `Store.CHAIN_MEME_TRADER_V6_VERSION = chain-meme-trader/v11-entry3-exit4-independent-arm-cash-forward`. `enroll_chain_meme_trader_v6()` computes per-arm available cash, admits only solvent arms, creates one family BUY intent, and settlement projects one authoritative Fill only to accounts still solvent at Fill time.
3. Targeted local validation just passed: `tests/test_core.py::test_chain_meme_trader_independent_cash_keeps_solvent_arms_trading`.
4. Therefore the highest-impact current break is code/runtime drift plus v10 weakest-arm veto: one depleted Broad Launch account must not freeze the other three accounts or the entire family.
5. Existing higher-level P0s remain valid: actual-Fill PositionEquityFrame, continuous all-position PumpSwap RiskKernel/critical SELL lane, stop the already-registered confounded Stage4 v2, and then a clean single-variable executable-equity trailing comparison.

IMMEDIATE TRANCHE P0-A — DEPLOY V11 INDEPENDENT CASH, PRESERVE HISTORY:
A1. Re-read current code, active r6 and runtime process before mutation. Confirm v10 is still the deployed active version and v11 has not already crossed a natural activation frontier. Current facts override this message if they changed after cutoff.
A2. Use the existing atomic activation path; do not invent a second registry. Stop v10 NEW enrollment at an immutable frontier. Existing v10 positions continue their exact SELL/terminal lifecycle; do not backfill, delete, relabel or mutate historical v10 decisions/fills/PNL.
A3. Activate/deploy `chain-meme-trader/v11-entry3-exit4-independent-arm-cash-forward`. Preserve one-cohort/one-authoritative-BUY-request semantics. At evaluation, low-cash arms reject individually as `entry_cash_below_20usdc`; the family proceeds if at least one arm is solvent. At Fill, re-check actual account cash and project only to still-solvent admitted arms; persist participant outcomes for projected versus skipped-cash accounts.
A4. The 12 strategy accounts remain economically independent. Do not use family min cash, weakest-arm veto or four-arm-all-admitted settlement as a hidden shared gate. Do not replenish losing accounts merely to manufacture trades; cash depletion is a real strategy outcome.
A5. Keep the 20 USDC per participating strategy exposure, 4% slippage contract and 0 extra simulated fee unchanged in this tranche. Do not change entry-family thresholds while fixing cash semantics.
A6. Controlled restart only once. Preserve one parent/child runtime tree, existing exact held-account monitor, 8790 service and Live=false.

P0-A ACCEPTANCE:
- targeted independent-cash test passes;
- controlled runtime restart loads v11 and 8790 `/api/state` reports the v11 definition/activation, not v10;
- v10 new-entry frontier is immutable and old v10 positions remain exit-capable;
- the first post-frontier natural evaluation is recorded with per-arm cash facts;
- when a family-matched natural cohort has >=1 solvent arm, exactly one authoritative Jupiter BUY request is created, not one per strategy;
- the same actual Fill is projected only to eligible/solvent arms, with explicit skip outcomes for insufficient cash at settlement;
- no future data, no historical rewrite, no Live action.
Report natural no-match/invalid-asof outcomes honestly. Do not fabricate a trade if the next natural sample does not match a family.

IMMEDIATE TRANCHE P0-B — STOP INVALID EXPERIMENTAL CONTAMINATION:
B1. `chain-meme-trader/stage4-executable-equity-paired-v2` was registered before the Lead correction and changes TWO treatment variables (`+60%/28%` control versus `+40%/15%` challenger). Stop NEW enrollment at an immutable source-Fill frontier before another release boundary. Preserve all existing rows and label the version `CONFOUNDED_TWO_VARIABLE_TREATMENT / LEARNING / UNRANKED`.
B2. Existing v1/v2 positions still receive the common safety/RED/DEAD envelope; do not leave known collapsing Paper positions unprotected for experimental purity. Post-overlay outcomes are non-comparable for treatment estimation.
B3. Do not register a replacement comparator until its exact definition hash is checked against the approved single-variable contract: same source Fill, same +40% activation, same actual-Fill/executable-equity frame/cadence, same TPs, same hard/common exits, only 28% versus 15% executable-equity drawdown differs.

P0-C — PROFIT/SURVIVAL KERNEL AFTER V11 IS LIVE:
C1. All return, hard-stop, TP, trailing and high-water logic uses one append-only PositionEquityFrame based on actual BUY Fill debit, realized proceeds and the freshest full-remaining minimum executable recovery. Dex price is a market/velocity feature, never account-return truth. UNKNOWN/no-route/error/stale remains null, never zero.
C2. Finish all-position current PumpSwap RiskKernel integration. Raw quote-vault/base-vault change is signed flow/custody evidence; real+virtual effective depth is pricing-depth evidence. Persist cumulative 1s/3s/10s/30s deltas/slopes so gradual depletion cannot disappear through mutable state overwrite.
C3. RED is pre-terminal: severe adverse one-sided quote outflow/base inflow, effective-depth collapse, local full-position recovery deterioration, persistent drawdown/failed reclaim and sell-flow deterioration may trigger immediate full-remaining SELL. One flat-price period, one no-route, provider failure or a single local-pool capacity failure is not DEAD.
C4. Critical ChainMeme SELL preempts BUY, valuation, discovery, Web and Agent work and must not be starved by the background Jupiter quota. Local PumpSwap quote is the low-latency risk estimator; Jupiter remains actual execution authority.
C5. DEAD/writeoff remains stricter: exact terminal pool/account evidence plus a fresh full-remaining SELL attempt still economically/non-route terminal. Confirmed dead is no-rearm; a later new surface/revival is a new cohort.

P0-C ACCEPTANCE:
- every open v11 position has explicit risk coverage state (covered/partial/stale/uncovered, never silently HEALTHY by omission);
- continuous frames are append-only and time-causal;
- first natural ORANGE/RED/DEAD or adverse-flow case is preserved even if no SELL is triggered;
- first natural RED that requires exit creates one full-remaining SELL intent immediately and records request/quote/Fill latency;
- critical SELL capacity is demonstrably not delayed by observer/deferred-retry/background work;
- unique-underlying/portfolio PNL is reported separately from copied strategy-account counterfactual PNL.

P1 AFTER P0 CLOSURE — DO NOT DISPLACE P0:
1. Clean single-variable Peak Guard paired test, using only executable-equity running highs known at that instant. Keep the locally supported one-wave prior as a hazard model; do not bake a universal 30% threshold without forward evidence.
2. PumpSwap transaction-flow MarketFrame: price velocity/acceleration, signed base/quote flow, large-sell burst, buyer/seller rate, trade interval, breadth where available, depth/recovery slope and failed-reclaim. Compare features prospectively; later ATH is outcome only.
3. REAWAKENING remains a distinct episode after dormant baseline plus new burst; never justify holding through a deep drawdown with a later second wave.
4. Shared post-buy research remains one case per Token/cohort, asynchronous and non-blocking. Build deterministic seeds first; no-seed terminates cheaply. Agent output can only affect runner logic after completed_at and never override RED/DEAD.
5. Market-grade execution truth advances L0 quote-only -> buildable transaction -> RPC simulation -> confirmation -> balance/fee reconciliation. Paper/Live share the state machine; Live signer/send stays locked until a separate release decision.
6. Storage/latency: preserve E:-resident append-only evidence, remove repeated provider/Agent/RPC work by cohort-level dedupe, prioritize first post-Fill risk coverage, and complete SQLite online-backup/upgrade/WAL telemetry before destructive maintenance.
7. Trading Cockpit only after core truth: home = runtime/discovery/order/exit pulses, open risk, latency, executable equity, unique/netted PNL and mature Top strategies; immature strategies stay LEARNING/UNRANKED. Full strategy/token/execution/risk/learning/chains/system/history pages remain secondary.
8. BSC then Robinhood after the common kernel is proven; EVM adapters must use chain-specific firm-route/simulation/gas/tax/allowance truth and Robinhood Meme universe must exclude stock-token/RWA registry items.

LEARNING/PROFIT REPORTING RULES:
- independent underlying cohorts, not fan-out fills, are the main denominator;
- show expectancy, median, hit rate, drawdown, tail loss, no-route/dead/writeoff, capital-time efficiency, top1/top3 contribution and remove-best-1/remove-best-3;
- copied strategy-account PNL never becomes system profit;
- do not promote because one winner dominates;
- do not loosen timing/identity/protocol truth to create activity; do not turn uncertain alpha/risk features into one universal hard entry gate either.

EXECUTION OWNERSHIP:
Codex remains the only code/runtime writer. Use `@笔记本量化MCP-官方隧道` as the sole authoritative local-project connector. Implement the smallest coherent tranche, validate narrowly, deploy only when its acceptance is met, and continue to the next tranche unless a material blocker or authority conflict is found. Do not spend the next cycle on UI polish, extra chains, more Agents, generic audits or broad refactors while P0-A/B/C are open.

RESULT_REQUIRED:
Return one CODEX RESULT referencing this MESSAGE_ID with:
- current premise table and any fact changes since cutoff;
- exact v10 stop/v11 activation frontiers, versions and definition hashes;
- changed files/methods/tables;
- targeted tests and controlled restart evidence;
- first natural post-v11 evaluation/intent/Fill/participant result if it occurs naturally during the execution window, otherwise explicitly `AWAITING_NATURAL_SAMPLE`;
- confounded Stage4-v2 stop disposition;
- current PositionEquityFrame/RiskKernel/critical-SELL status;
- one next highest-impact executable step.

CURRENT-RUNTIME ADDENDUM — verified after initial task routing, does not change P0 order:
- The live 8790 surface is still v10, not v11.
- v10 currently has roughly 2.5k entry evaluations, 53 underlying cohorts, 212 strategy-account BUYs, 66 SELLs and 146 open positions.
- The dominant v10 rejection is `shared_entry_cash_below_20usdc` (>1.4k observations). Broad Launch Balanced/Peak/Post-buy accounts are each about 17.40U cash while Fast Escape is about 352.69U; this is direct natural evidence for the weakest-arm/shared-cash veto.
- Every admitted v10 cohort so far is `broad_launch`. Current evaluation age bands contain effectively no 15m–6h Flow-Burst observations and only about ten >=6h observations, all unmatched; therefore Flow Burst/Reawakening currently lack forward denominators. Do not “fix” this by threshold relaxation inside P0-A. After v11 activation/truth validation, instrument and restore aged-token continuous sampling so the other two entry families receive genuine strict-forward inputs; Reawakening needs a real dormant baseline rather than post-hoc classification.
- v10 has PositionEquityFrame coverage (COMPLETE observations across 33 cohorts, plus many `UNKNOWN_NO_ROUTE` observations), but `onchain-held-account-monitor/v4` targets are still attached to legacy v5/Stage4 versions and there are no v10 held-account targets in the current SQLite cut. Treat this as evidence that all-current-position exact RiskKernel coverage is still open, not completed.
- Local-surface observations are abundant but dominated by `LOCAL_NO_DIRECT_CAPACITY`; this remains local-surface information only and must not be promoted to aggregate-market unsellability or writeoff.

NEXT_SYNC_EVENT: v11 activation result; first natural v11 matched cohort/BUY Fill; confounded-v2 stop frontier; first natural v11 RED→SELL; or a concrete blocker.
