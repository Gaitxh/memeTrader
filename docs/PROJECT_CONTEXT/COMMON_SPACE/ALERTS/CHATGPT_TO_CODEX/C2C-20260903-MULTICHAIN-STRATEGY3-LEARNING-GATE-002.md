# C2C-20260903-MULTICHAIN-STRATEGY3-LEARNING-GATE-002

PRIORITY: P0 / USER-EXPLICIT + RELEASE-GATE
TYPE: HANDOFF / DESIGN_CORRECTION / IMPLEMENTATION_DIRECTIVE
OWNER: Codex
FACT_CUTOFF_UTC: 2026-09-03T04:15:00Z
BLOCKS_NEXT_CONTROLLED_RESTART: true
BLOCKS_LIVE: true

## Latest user supersession

The user's newest explicit instruction supersedes the immediately prior temporary Solana-only priority: implement BSC, Base and Robinhood Chain in the simulation system, keep chain identity visible, and use chain-appropriate fee/cost semantics. Solana remains required; scope is now four-chain. Historical data/code must remain. Live stays locked.

Lead has already changed ignored local `config.json` discovery/candidate lists back to `solana,bsc,base,robinhood`; do not treat the earlier Solana-only config as authoritative on the next restart. Re-read config before deploy.

## Current facts that change the plan

1. A new fair epoch exists: `fair-comparison/2026-09-03-20usdc-v2`, started `2026-09-03T03:37:02.354538Z`, $1000 per strategy; prior main Paper $1001.7324747 / 11 historical trades are preserved but excluded.
2. Frozen current cost experiment is $20 entry notional, 4% adverse slippage each side and $0.40 per economic fill. This is intentionally conservative and must be labeled `modeled/frozen`, not real chain fee.
3. Current new versions are `onchain-only-shadow/v2-20usdc`, Jupiter v2 20usdc/400bps, exploration v4, exit challenger v4, narrative runner v2, context v3.
4. New v2 onchain shadow has 7 cohorts at this cutoff, including 4 Solana, but Jupiter v2 has 0 attempts/results. Because anchors are >30s old, this is not merely “no opportunity”; diagnose quote-lane dispatch/registration/current-source drift before interpreting Strategy 2/3 zero trades.
5. Current checkout source is ahead of the running 03:33 UTC process. `runtime.py` passes `max_liquidity_impact_pct` to `register_onchain_paper_exploration`, while current `store.py` signature does not accept it. `data/logs/runtime-crash.log` records repeated TypeError on restart. Codex is currently running pytest; fix source consistency and targeted startup test before next restart. Do not kill the healthy old process until the new source is startable.
6. Strategy 3 causal design is currently confounded: `register_onchain_paper_narrative_runner()` sets `source_baseline_exit` to the dynamic exit challenger. Therefore, with narrative runner disabled, Strategy 2 fixed-horizon baseline and Strategy 3 can still exit differently. Old v1/v2 historical rows remain immutable, but the new fair epoch has no current Strategy 2/3 positions yet. Correct the next narrative-runner version before first new paired BUY: while treatment is disabled, Strategy 3 must mirror Strategy 2 fixed-baseline exits exactly; only a separately registered narrative treatment may create post-entry divergence.
7. Learning is active as evidence collection, not mature online strategy adaptation: token-universe ~117k cohorts/~341k outcomes; information-first 193 cohorts; Token Context 1079 assessments/1039 outcome cohorts with 0 mature labels; creator risk 2304 cohorts; liquidity-survival v3 ~1905 cohorts/~7450 outcomes; source utility only 5 distinct closed Paper outcomes across 4 days; attention experiment 120 assignments but 0 outcomes. `watch_attention_policy` still applies 1.0 multiplier and requires preregistered randomized evidence. Do not claim strategy auto-optimization is active.

## Required four-chain architecture

Do not solve the user's fee request by merely assigning four arbitrary static fees. Carry chain identity from Token -> candidate -> route -> position -> trade -> PNL and split costs into explicit components:

- route/venue fee (embedded in router/min-output where available),
- adverse slippage / minimum-output protection,
- token buy/sell tax,
- network execution fee,
- L2/L1 data/security fee where applicable,
- approval/allowance cost where applicable,
- optional conservative fallback only when a component is unavailable.

Every fill/position must expose `chain`, `execution_quality` (`executable_quote` vs `modeled`), `fee_model_version`, fee components and total. Never combine modeled EVM PNL with executable-quote PNL without labeling/breakdown.

### Solana
Use amount-specific Jupiter minimum output for Strategy 2/3; fix current v2 dispatch first. Network fee should prefer observed transaction-order fee fields when a safe read-only transaction build/simulation path is registered; the current $0.40 remains the frozen fair-test fallback until replaced by a new version. Main information-first Paper must eventually move from Dex mark±slippage to final policy-size Jupiter execution challenger before it can be called executable.

### BSC
Enable discovery/candidate after current source consistency is fixed. Require EVM security evidence. Prefer amount-specific aggregator/firm route (0x if configured) over Uniswap-V3-only pool math; otherwise keep direct-quoter results `modeled/research`. Include BNB gas, token tax/honeypot/max-sell/transfer restrictions and route failure. Honeypot.is simulation is especially useful here.

### Base
Require amount-specific route, token safety, L2 execution gas and L1 data/security fee. Do not call `gasUsed*gasPrice` complete cost. Use 0x totalNetworkFee and/or Base GasPriceOracle semantics when transaction bytes are available. Keep exact chain marker and accounting currency.

### Robinhood Chain
Chain id 4663. Remove the hard-coded `execution_safety_unsupported_chain` only after GoPlus 4663 support is actually integrated/tested. Add 4663 to EVM security enrichment. Before Meme candidate/paper, exclude official Robinhood Stock Token/RWA contracts by exact official address set/version; do not classify generic ERC20 stock tokens as Meme. Route/gas must be independent of Base/BSC. Current Uniswap-V3 research already produced one natural quoted result, but it remains cost_unknown and is not sufficient for Paper.

## Strategy model after multichain

Keep three strategy accounts; do NOT create one account per chain. Add chain breakdown inside each strategy so the experimental question remains strategy-based rather than UI-account explosion:

1. Strategy 1 — information + Token; chain-eligible candidate with chain-specific execution gate.
2. Strategy 2 — token-only baseline; per-chain amount-specific execution adapters, same $20 fair notional unless a future sizing experiment supersedes it.
3. Strategy 3 — same exact Strategy 2 entry; initially exact same Strategy 2 baseline exit. Post-entry narrative/creator/community watch is the treatment candidate; runner remains disabled until preregistered maturity.

Expose per strategy: total cash/realized/executable-unrealized, chain breakdown, modeled-vs-executable coverage, no-route/unpriced positions, fee components, trade counts, drawdown. Do not sum unknown/unexecutable marks into PNL.

## Strategy 3 disposition

KEEP THE RESEARCH QUESTION, REVISE THE IMPLEMENTATION. It is valuable because it estimates the incremental value of post-entry information conditional on the same token entry. It is not a third selector. Correct control purity before collecting the new fair-version cohort. The first promoted treatment should be event-driven, not constant LLM polling: new independent source, correction/denial, narrative-state change, creator/LP anomaly. Deterministic risk/route exits always override narrative.

## Learning/promotion pipeline

Stop treating more Shadow tables as completion. Add/finish an explicit promotion state per research family:
`COLLECTING -> MATURE_DESCRIPTIVE -> CHALLENGER_PREREGISTERED -> FORWARD_CHALLENGER -> HOLDOUT_PASS -> PROMOTABLE/REJECTED`.
No online self-edit. Candidate features to promote only after mature evidence: liquidity survival, creator launch history, market microstructure components, source utility, social/narrative state, first-N buyer/holder-role once valid.

## Immediate ordered implementation

P0-0. Finish current pytest and repair source/runtime signature mismatch; targeted startup construction test. Keep old runtime until replacement is proven startable.
P0-1. Diagnose/fix current Jupiter v2 0-attempt dispatch before interpreting zero Strategy 2/3 trades.
P0-2. Register corrected Strategy-3 control version before first new fair BUY; baseline exit must mirror Strategy 2 exactly while narrative treatment disabled.
P0-3. Four-chain enablement: config/defaults + candidate lists + Robinhood 4663 safety + official Stock Token/RWA exclusion + chain status UI.
P0-4. Implement chain-aware execution-cost interface with explicit components and truth tier. Reuse existing EVM route ledger, but do not promote Uniswap-V3 pool math alone as executable Paper. Prefer 0x/firm aggregator where configured; no secret logging.
P0-5. Add per-strategy chain breakdown and fee/execution-quality UI; collapse deep research by default.
P1. Mature/promotion pipeline: liquidity survival/creator/microstructure/social/first-N buyer. No threshold changes from retrospective stats.

## Acceptance before next controlled restart

- current source can construct Runtime and targeted tests pass;
- no current Strategy-3 fair-version position exists under the confounded exit definition, or the old registration is explicitly abandoned-before-first-position and a corrected version registered;
- four-chain configuration is explicit and UI chain status matches backend truth;
- Robinhood is not silently admitted without 4663 security + Stock Token/RWA exclusion;
- EVM quote-only results remain excluded from executable PNL until full cost/sellability semantics are present;
- Live false/locked; no backfill; no Git push.
