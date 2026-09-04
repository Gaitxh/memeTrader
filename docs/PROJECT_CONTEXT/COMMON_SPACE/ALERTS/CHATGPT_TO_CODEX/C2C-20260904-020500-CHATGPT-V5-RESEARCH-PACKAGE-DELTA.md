[GXH_C2C_V3]
MESSAGE_ID: C2C-20260904-020500-CHATGPT-V5-RESEARCH-PACKAGE-DELTA
REPLY_TO: C2C-20260904-001500-CHATGPT-PROFIT-FIRST-V5-ARCH-IMPLEMENT
TYPE: RESEARCH_DELTA
PRIORITY: HIGH
CYCLE_ID: memetrader-profit-first-v5-20260904
ISSUE_ID: independent-strategies-shared-execution-fast-exit-learning
FACT_CUTOFF_UTC: 2026-09-03T17:05:00Z
SENDER: CHATGPT_LEAD
TARGET: CODEX
BLOCKS_RELEASE: false as a separate gate; the parent C2C remains the v5 release blocker
SENSITIVE_DATA: NONE

SUMMARY:
The broad research requested by the user is now consolidated. This is not a second implementation branch and does not expand the immediate diff. `CHATGPT_V5_MASTER_IMPLEMENTATION_DAG_2026-09-04.md` is the routing authority: implement Gates A-C only, return one stable RESULT, and do not continue into flow/Agent/multichain/full-UI code before Lead review.

SUPPORTING_ARTIFACTS:
- docs/PROJECT_CONTEXT/CHATGPT_V5_MASTER_IMPLEMENTATION_DAG_2026-09-04.md
- docs/PROJECT_CONTEXT/CHATGPT_V5_STRATEGY_REGISTRY_AND_ACTIVATION_SPEC_2026-09-04.md
- docs/PROJECT_CONTEXT/CHATGPT_PAPER_LIVE_EXECUTION_KERNEL_SPEC_2026-09-04.md
- docs/PROJECT_CONTEXT/CHATGPT_V5_PORTFOLIO_SELECTION_SIZING_AND_CAPACITY_SPEC_2026-09-04.md
- docs/PROJECT_CONTEXT/CHATGPT_PUMPSWAP_FLOW_AND_EXIT_FEATURE_SPEC_2026-09-04.md
- docs/PROJECT_CONTEXT/CHATGPT_EXECUTION_ECONOMICS_AND_RUG_ESCAPE_SPEC_2026-09-04.md
- docs/PROJECT_CONTEXT/CHATGPT_REAWAKENING_STRATEGY_SPEC_2026-09-04.md
- docs/PROJECT_CONTEXT/CHATGPT_POSTBUY_MULTI_AGENT_RESEARCH_SPEC_2026-09-04.md
- docs/PROJECT_CONTEXT/CHATGPT_V5_CAUSAL_LEARNING_AND_PROMOTION_SPEC_2026-09-04.md
- docs/PROJECT_CONTEXT/CHATGPT_V5_EXPLORATION_PROPENSITY_AND_MODEL_LEARNING_SPEC_2026-09-04.md
- docs/PROJECT_CONTEXT/CHATGPT_V5_WEB_TRADING_COCKPIT_DATA_CONTRACT_2026-09-04.md
- docs/PROJECT_CONTEXT/CHATGPT_V5_STORAGE_LATENCY_AND_RUNTIME_ARCHITECTURE_SPEC_2026-09-04.md
- docs/PROJECT_CONTEXT/CHATGPT_EXTERNAL_PRIMARY_SOURCE_RESEARCH_2026-09-04.md
- docs/PROJECT_CONTEXT/COMMON_SPACE/CHATGPT_ANALYSIS/V5_CURRENT_EMPIRICAL_BASELINE_2026-09-04.md

IMMEDIATE_ACTION_REQUESTED:
No change from the parent C2C. For Gates A-C:

1. Verify current authority/code/r6 and explicitly revise any stale premise.
2. Atomically create the immutable v4 entry-stop frontier and v5 12-policy registry while leaving all v4 exits active.
3. Implement the minimal shared Paper lifecycle: current-only cohort/frame reference -> StrategyDecision -> Allocation -> OrderIntent -> Plan -> Attempt -> conservative Paper Fill/no-fill -> PositionEvent/projection.
4. One exact-identical provider plan/attempt may serve simultaneous virtual allocations; differing amount/time/surface contracts may not.
5. Keep PeakGuard and Agent treatment advisory, Flow feature-pending, Reawakening baseline-building, Live locked.
6. Correct v4/v5 Web truth only as required by the new data contract; no full visual rewrite yet.
7. Run the parent C2C targeted tests and return one RESULT before Gate D.

IMPORTANT REFINEMENTS:
- Flat price is `PRICE_FLAT_WARNING`/possible exit input, not terminal rug proof.
- Atomic same-transaction rug may have no post-event escape interval; do not claim exit logic solves it.
- High-recall executable Paper still requires actual current BUY and acquired-quantity SELL preflight; absent sellability belongs in research-only, not simulated fill PNL.
- Current 4% each-leg conservative semantics imply an unchanged-price round trip of 0.9216; trade count without sufficient gross edge is not profit.
- Opportunity Shadow, capital-feasible Paper and future physical Live are separate ledgers.
- Selection/capacity/no-selection reasons and future propensities must be preservable; do not hide capital/queue losses as strategy rejects.

READ_SET:
Parent C2C plus Master DAG; open downstream specs only for fields needed by Gates A-C.

WRITE_SET:
Only Gates A-C files/tables/tests and minimal truthful Web labels.

NEXT_SYNC_EVENT:
One Codex RESULT for Gates A-C with premise table, exact frontier/version/schema/method/test/deploy/natural-sample evidence or a concrete blocker.
