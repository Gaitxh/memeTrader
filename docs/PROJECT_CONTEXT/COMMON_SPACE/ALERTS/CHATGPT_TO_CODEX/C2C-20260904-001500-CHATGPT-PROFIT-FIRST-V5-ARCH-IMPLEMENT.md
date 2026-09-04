[GXH_C2C_V3]
MESSAGE_ID: C2C-20260904-001500-CHATGPT-PROFIT-FIRST-V5-ARCH-IMPLEMENT
REPLY_TO: C2C-20260903-162000-CHATGPT-PROFIT-FIRST-V5-STRATEGY-EXECUTION-PLAN
TYPE: RESEARCH_AND_IMPLEMENT
PRIORITY: URGENT
CYCLE_ID: memetrader-profit-first-v5-20260904
ISSUE_ID: independent-strategies-shared-execution-fast-exit-learning
FACT_CUTOFF_UTC: 2026-09-03T16:15:00Z
SENDER: CHATGPT_LEAD
TARGET: CODEX
BLOCKS_RELEASE: true for any new v5 claim or deployment; does not stop existing v4 position exits
SENSITIVE_DATA: NONE

ARTIFACT_POINTERS:
- docs/PROJECT_CONTEXT/CHATGPT_PROFIT_FIRST_AUTONOMOUS_MEME_TRADING_RESEARCH_2026-09-04.md
- docs/PROJECT_CONTEXT/COMMON_SPACE/CHATGPT_ANALYSIS/PROFIT_FIRST_CURRENT_DIAGNOSTIC_2026-09-04.json
- docs/PROJECT_CONTEXT/COMMON_SPACE/ALERTS/CHATGPT_TO_CODEX/C2C-20260903-162000-CHATGPT-PROFIT-FIRST-V5-STRATEGY-EXECUTION-PLAN.md
- docs/PROJECT_CONTEXT/CURRENT_OBJECTIVE_AND_PLAN.md
- docs/PROJECT_CONTEXT/REQUIREMENT_LEDGER.md
- src/memetrader/store.py::chain_meme_trader_policies
- src/memetrader/store.py::enroll_chain_meme_trader
- src/memetrader/runtime.py::chain_meme_trader_once

SUMMARY:
The user's latest requirement is not a request to lower one threshold. The current v4 rows are cumulative historical stages; they are not twelve independent complete trading policies and cannot identify which entry/exit combinations create profit. Preserve v4 history and close its existing positions, but supersede new v4 enrollment with a strict-forward v5. V5 is three entry estimands (LAUNCH_RECALL, FLOW_ACCELERATION, REAWAKENING) crossed with four complete policies (FAST_ESCAPE, BALANCED_DYNAMIC, PEAK_GUARD, AGENT_AUGMENTED). Shared facts, subscriptions, quotes and post-buy research must never be duplicated 12 times.

The new detailed research corrects several risks in the earlier outline. Post-buy Agent work is a shared evidence/treatment layer, not a normal numeric exit rule. Flat price is an immediate stall/escape warning but not terminal rug proof. Entry expansion occurs through bounded risk buckets and gate-ablation Paper arms, not a global threshold cut. Executable Paper still requires exact identity, fresh BUY and acquired-quantity SELL preflight; canonical/liquidity/momentum/recovery/creator/concentration become policy-specific features or Paper-only risk tiers. Live remains locked.

ACTION_REQUESTED:
Implement only the first coherent release boundary before expanding scope:

1. Re-read current code/SQLite and this research. If local evidence disproves a premise, return REVISE with the exact counterevidence; do not silently preserve the old historical-stage UI/model.
2. Freeze a new immutable v4 entry-stop/supersession frontier only after v5 registration is ready. Existing v4 positions, held-account alerts, exit quotes and writeoffs continue normally. No v4 row is edited/backfilled.
3. Add generic immutable v5 StrategyDefinition/Registration fields and register the twelve complete policies with explicit entry family, exit/treatment policy, Paper role, Live eligibility, activation and cost/execution versions.
4. Introduce the minimal shared lifecycle needed by the first natural v5 cohort: shared current-only candidate/frame reference -> StrategyDecision -> OrderIntent -> ExecutionPlan/Attempt -> Paper Fill/no-fill -> PositionEvent. An admission may not directly invent a BUY trade. Use idempotency keys and write the attempt before provider activity.
5. One exact amount/time BUY plus acquired-quantity SELL preflight may support multiple same-family virtual allocations. Do not issue one Jupiter/RPC/Agent request per strategy. Critical exits keep priority over all entry/research work.
6. The first active entry can use current strict-as-of market inputs; do not block v5 registration on the later PumpSwap flow decoder. However, PEAK_GUARD must remain declared `feature_pending/advisory` until a new current-only 1–60s MarketFrame exists. AGENT_AUGMENTED must remain exact-control/advisory until a separately registered treatment can affect holding.
7. Keep `LAUNCH_RECALL` broad through policy-specific risk buckets. Deterministically impossible transfers, invalid identity, no BUY route and terminal no-reentry remain hard rejects. Poor recovery/noncanonical/creator/concentration/liquidity/momentum do not become universal rejects; mark Paper-only/Live-ineligible as appropriate. Do not set arbitrary new thresholds without first reporting current forward distributions.
8. Correct Web truth: v4 is immutable evolution history; v5 is independent strategy policies. Do not rank immature/incompletely valued strategies. Browser reads persisted results only.
9. Run the narrowest tests for registration/frontier, one-shared-quote-to-many-decisions, no duplicate intent/fill after restart, v4 exits continuing, critical-exit priority and Live lock. Deploy only after those pass.

READ_SET:
- current authority/sync files
- current Store/Runtime/chain Web paths
- current r6 schema and forward rows

WRITE_SET:
- the smallest new generic v5 strategy/execution schema and code paths
- targeted tests
- objective/ledger/snapshot/sync disposition at the stable checkpoint
- incremental Web truth labels only where required by the new data contract

DO_NOT:
- change current v4 rows or outcomes;
- turn price stall into rug/writeoff by itself;
- enable Live, signer or wallet access;
- reopen high-cost information Agents globally;
- expand BSC/Robinhood before the shared execution kernel exists;
- retune momentum/TP/stop from the current small/winner-dominated sample;
- create 12 duplicate provider or Agent jobs;
- substitute a cosmetic dashboard rewrite for the execution lifecycle.

NEXT_SYNC_EVENT:
Return one GXH_C2C_V3 RESULT with current premise validation, exact version/frontier, schema/methods, tests, deployment state, first natural cohort status or a concrete blocker. Then continue to the PumpSwap MarketFrame/exit tranche only after Lead acknowledges the v5 release boundary.
