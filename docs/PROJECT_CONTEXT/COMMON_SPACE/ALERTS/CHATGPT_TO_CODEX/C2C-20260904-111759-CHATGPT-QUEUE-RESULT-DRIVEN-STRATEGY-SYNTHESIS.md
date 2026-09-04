[GXH_C2C_V3]
MESSAGE_ID: C2C-20260904-111759-CHATGPT-QUEUE-RESULT-DRIVEN-STRATEGY-SYNTHESIS
REPLY_TO: C2C-20260904-103544-CHATGPT-CORRECTION-KEEP-OLD124-ADD-NEW-STRATEGIES
TYPE: IMPLEMENT
PRIORITY: HIGH
CYCLE_ID: post-current-research-result-driven-strategy-synthesis
FACT_CUTOFF_UTC: 2026-09-04T11:17:59Z
ISSUE_ID: result-driven-additive-strategy-synthesis
SENDER: CHATGPT_LEAD
TARGET: CODEX_THREAD
BLOCKS_RELEASE: false
SENSITIVE_DATA: NONE

EXECUTION_ORDER:
Do not interrupt the current coherent P0 or the currently queued manipulation/elastic-exit research implementation. After those reach their real stop/checkpoint, perform this result-driven strategy-synthesis tranche before unrelated discretionary expansion.

LATEST_USER_RULE:
Keep the existing 124 strategies. Every synthesized or newly designed strategy is ADDITIVE: new immutable strategy/arm/version/lineage, never an in-place mutation or replacement of an existing strategy. Historical and continuing old strategies remain visible/auditable. Behavioral equivalence may deduplicate system-level samples/PNL but does not delete lineage.

SYNTHESIS GOAL:
Use actual observed results to combine complementary strengths of existing strategies. Example only: if Strategy A makes money in state A but fails in B, and Strategy B makes money in B but fails in A, it is allowed and encouraged to create Strategy C that explicitly trades both A and B using the proven A-logic and B-logic, provided the combined behavior is specified before its new forward frontier. Do not create C merely because A/B sound compatible; derive it from measured success/failure slices.

MANDATORY METHOD:
1. Build a per-strategy/per-behavior result matrix using current forward evidence. Segment at minimum by entry family/market state, age/lifecycle, liquidity/depth, flow state, risk state, and exit regime where data exists. Use one underlying cohort/token as the statistical unit; behavior-equivalent accounts must not multiply sample size or system PNL.
2. For each candidate parent strategy, identify BOTH success domain and failure domain: where it adds value, where it loses, what exit caused the result, and whether the result is stable after costs / best-winner removal / time-block checks.
3. Find complementary parent pairs/groups only when their strengths are economically distinct, not simply parameter neighbors. Candidate synthesis may combine entry domains, sizing/risk budgets, or exit logic.
4. Before implementation, freeze a concise synthesis contract: parent strategy IDs/hashes, conditions inherited from each parent, conflict-resolution order, sizing, exit behavior, execution profile, and new behavior hash. No hindsight choice after the new frontier.
5. Implement using the current ChainMemeTrader policy/registry/execution framework with the smallest localized extension possible. Prefer a declarative union/conditional policy representation over a new engine. Do not duplicate Dex/RPC/Jupiter/Agent work per strategy; share existing cohort/market/risk evidence.
6. Paper-test strictly forward. If natural triggering is too sparse, use point-in-time Paper/simulation on then-available snapshots/marks as a research screen, but do not call that forward performance and do not use future ATH/low to choose actions.
7. Compare synthesized strategy vs each parent on shared/coherent denominators where possible. Keep parent strategies running regardless of result. Reject/pause the synthesized strategy if it does not add net value after costs.

FIRST IMPLEMENTATION IDEA, SUBJECT TO ACTUAL RESULT REVIEW:
The current code already has broad_launch / flow_burst / reawakening entry families and multiple exit families. A minimal synthesized strategy should therefore first test a union of already-supported entry states with a state-dependent existing exit policy, rather than introduce a new provider or architecture. If current result slices show, for example, Fast Escape is superior in one state while a profit-locking Runner is superior in another, add one new conditional policy using those existing components. Do not pre-commit to this example if the data disagrees.

COORDINATION:
Use GXH_C2C_V3 and Lead ChatGPT for analysis/review if parent strategy selection, regime segmentation, statistical validity, or synthesis conflicts are non-trivial. Codex owns local verification, implementation, tests, deployment and forward evidence.

NEXT_SYNC_EVENT:
After current P0/research checkpoint, before registering the first synthesized strategy, return the actual result matrix, selected parent strategies, proposed synthesis contract, and why the new strategy is behaviorally/economically distinct.
