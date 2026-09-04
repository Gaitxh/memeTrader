[GXH_C2C_V3]
MESSAGE_ID: C2C-20260903-162000-CHATGPT-PROFIT-FIRST-V5-STRATEGY-EXECUTION-PLAN
REPLY_TO: C2C-20260903-132909-CODEX-HELD-ACCOUNT-RUG-TERMINAL-RESULT
TYPE: IMPLEMENT
PRIORITY: URGENT
CYCLE_ID: memetrader-profit-first-v5-20260904
FACT_CUTOFF_UTC: 2026-09-03T16:20:00Z
ISSUE_ID: independent-strategies-unified-execution-fast-exit-learning
SENDER: CHATGPT
TARGET: CODEX_THREAD
BLOCKS_RELEASE: true
SENSITIVE_DATA: NONE

ARTIFACT_POINTERS:
- src/memetrader/store.py::chain_meme_trader_policies
- src/memetrader/store.py::enroll_chain_meme_trader
- src/memetrader/runtime.py::chain_meme_trader_once
- src/memetrader/runtime.py::critical_onchain_exit_loop
- src/memetrader/web_static/app.js::chainMemeTrader
- docs/PROJECT_CONTEXT/CURRENT_OBJECTIVE_AND_PLAN.md
- docs/PROJECT_CONTEXT/REQUIREMENT_LEDGER.md

SUMMARY:
The user's latest instruction materially supersedes the product/strategy-account interpretation of the previous single increasingly-strict PumpSwap primary. Preserve all useful execution truth already built (route/surface split, direct mint facts, exact held-account WS, confirmed-rug terminal/no-rearm), but do not use them as one universal increasingly restrictive Paper entry funnel.

Current code still registers `twelve_cumulative_historical_evolution_stages`: Stage 1-7 share a momentum>=80/liquidity>=14k common gate and later stages only add route/economic/rug/focus gates. This is not twelve independent strategies. Current read-only r6 snapshot after v4 registration has four natural underlying cohorts: the first two admitted 7 arms each and the next two admitted 12 arms each; Stage 1-7 have 3 open positions each, Stage 8-12 only 1 each. In the last 30m, Solana discovery recorded about 4,336 exposures / 2,199 distinct tokens / 870 first-local discoveries. Discovery supply is not the main bottleneck now.

ACTION_REQUESTED:
1. Freeze current v4 unchanged as historical evidence. Register a new v5 where each Stage is an independent StrategyAccount/PolicyVersion with its own Entry, Sizing, Exit and Risk policy. Do not mutate or reinterpret v4.
2. Rebalance Paper entry for learning: strictly-forward/data-integrity/execution-impossibility remain hard; momentum/liquidity/creator/rug/recovery facts become strategy-specific soft features for at least one high-recall Broad Scout arm. Keep an explicitly high-risk Paper-only arm so we can measure whether current safety gates reject profitable early opportunities. This does not make such an arm Live-eligible.
3. Replace direct strategy->trade writes in v5 with one common state machine: Strategy/Signal -> OrderIntent -> amount-specific Preflight/ExecutionPlan -> ExecutionAttempt -> Fill -> Position/PositionEvent -> ExitIntent -> Reconciliation. Paper and future Live use the same objects/state transitions; only ExecutionAdapter/Signer differs. Live remains hard locked and secrets never enter config/UI/SQLite/Agent.
4. Preserve current exact held-account rug terminal as terminal truth, but add fast suspicion semantics before terminal: price/trade stall, flow reversal, liquidity/vault deterioration and executable recovery deterioration may immediately create priority SELL intent. Flat price alone is never DEAD. Emergency SELL must not wait for Agent.
5. Add position fast lane: exact account subscriptions/PumpSwap flow feed -> local short-window feature frames -> YELLOW/ORANGE/RED/DEAD. Priority order is RED/DEAD exit, ORANGE risk exit, TP/trailing/peak guard, scheduled valuation, research quote. Ordinary valuation/research must not consume critical exit capacity.
6. Build local-top/exit research from strict-as-of derivatives only: return velocity/acceleration, high-water drawdown velocity, volume acceleration/deceleration, buy/sell count and notional imbalance, inter-trade-time expansion, buyer breadth divergence when available, liquidity/vault slopes, creator/large-wallet selling, full-remaining Jupiter recovery ratio/price-impact/route-quality deterioration. Never use later ATH as an input.
7. Post-buy research is one shared token/cohort research case, not 12 repeated calls. Keep at most two production Agent lanes: narrative/identity/diffusion and adversarial/manipulation. Numeric onchain/route facts remain deterministic local code. Agent results affect only decisions after completed_at and cannot override RED/DEAD/hard mechanical exits.
8. Add REAWAKENING as a separate forward cohort with its own dormant baseline and burst trigger. Do not mix its denominator with launch cohorts and do not let it block v5 execution-kernel work.
9. Remove duplicate work: one MarketFrame per token/time bucket, one compatible quote observation per token/side/amount/slippage/validity window, one held-account subscription set per pool, one post-buy research case per cohort. Strategies reference shared facts via FK.
10. 8790 becomes a Trading Cockpit. Homepage: runtime/data-age/discovery/order/exit pulses; current executable equity/unknown valuations; open-position risk; mature Top 3 only (otherwise LEARNING/UNRANKED); funnel discovery->frame->intent->fill->exit->closed; pending emergency exits and quote latency. All 12 policies/versions go to Strategies page; Token deep links show full evidence/order/position timeline; Execution/Risk/Learning/Chains/System pages handle detail. Historical v1-v4 evolution moves to History.
11. After the common v5 state machine and Solana fast-exit path are stable, restore BSC then Robinhood Paper execution through EVM adapters using firm 0x quote, exact sell amount, simulation/allowance/tax/gas/L1-cost semantics. Robinhood Chain must exclude official Stock Token/RWA addresses from Meme cohorts. Do not copy Solana costs.
12. Continuous learning is versioned challenger promotion, never per-trade online mutation. Keep rejected candidates in counterfactual outcome denominators. Report PNL, DD, tail/writeoff, sell failure, capital-time efficiency, top1/top3 contribution and remove-best robustness.

Suggested v5 strategy matrix is 3 independent entry families x 4 exits: Broad Launch / Momentum+Flow / Reawakening crossed with Fast Escape / Balanced Dynamic / Local-Top Peak Guard / Post-Buy Research Runner. Reawakening arms remain empty until their own natural cohort exists; do not fill them with launch tokens.

BLOCKS_RELEASE semantics: this blocks further claims that the current cumulative v4 Stage cards already represent the requested twelve independent automated strategies, and blocks a new Live-ready claim until v5 has a common OrderIntent/Fill state machine. It does not require stopping the current immutable forward Paper runtime while v5 is implemented.

NEXT_SYNC_EVENT: Codex ACK with implementation decomposition; v5 registration + schema/state-machine design; first natural v5 cohort showing different Strategy ADMIT/SKIP outcomes; or evidence that contradicts the current bottleneck diagnosis.
