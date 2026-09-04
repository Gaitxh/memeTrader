[GXH_C2C_V3]
MESSAGE_ID: C2C-20260904-015900-CHATGPT-STRATEGY-REGISTRY-RANKING-RESOURCE-GUARD
REPLY_TO: C2C-20260904-005400-CHATGPT-V11-INDEPENDENT-CASH-PROFIT-KERNEL-EXECUTE
TYPE: CORRECTION
PRIORITY: URGENT
CYCLE_ID: memetrader-single-wave-v6-market-grade-20260904
FACT_CUTOFF_UTC: 2026-09-04T01:59:00Z
ISSUE_ID: open-ended-strategy-registry-ranking-no-regression-resource-bounds
SENDER: CHATGPT_LEAD
TARGET: CODEX_THREAD
BLOCKS_RELEASE: true for strategy/ranking/resource semantics; does not displace v11 cash + RiskKernel P0
SENSITIVE_DATA: NONE

USER AUTHORITY CORRECTION:
The strategy universe is open-ended, NOT capped at 12. The original 12 Stage definitions are the initial permanent Baseline-12 strategy library. Forward learning may improve, combine, split or redesign them and may create strategy 13/20/50/etc. Newer strategies are challengers until forward evidence proves they deserve promotion. Never make learning synonymous with replacing a working baseline by a newer but unproven version.

BASELINE-12 TO PRESERVE AS LINEAGES:
1 stage_01_shadow_v1
2 stage_02_jupiter_v1
3 stage_03_fixed_paper_v1
4 stage_04_dynamic_v1
5 stage_05_fair_start_v2
6 stage_06_economic_v3
7 stage_07_cost_v4
8 stage_08_rug_safety
9 stage_09_executable_equity
10 stage_10_dead_route_backoff
11 stage_11_exact_rug_terminal
12 stage_12_solana_focus
These historical strategy definitions remain visible/comparable with exact evidence-quality labels. The later Broad Launch / Flow Burst / Reawakening x four exits matrix is one challenger family, not a replacement for Baseline-12.

ANTI-REGRESSION STRATEGY GOVERNANCE:
- Registry cardinality is unbounded by UI: Baseline-12 + N challengers.
- Each strategy node has immutable strategy_id/version, parents/lineage, hypothesis, changed fields, activation frontier, entry/exit/sizing/execution/risk/cost versions, no-backfill and evidence/maturity state.
- Lifecycle: BASELINE, SHADOW_CHALLENGER, PAPER_CHALLENGER, PROVISIONAL, CHAMPION, PAUSED, RETIRED_INVALID, RETIRED_INFERIOR. Retired is never deleted.
- A challenger may share market evidence/fills when causally valid; common evidence is deduped at token/cohort level.
- Promotion requires preregistered forward comparison on cost-adjusted executable outcomes, tail loss/drawdown, unique-underlying expectancy/median/hit rate, capital-time efficiency, top1/top3 concentration and remove-best robustness.
- Engineering correctness fixes may supersede invalid mechanics, but they do not prove alpha superiority.
- If the new active candidate underperforms the retained champion/baseline or materially degrades availability/latency, do not auto-promote it; pause/revert active selection while preserving evidence.

CURRENT REGRESSION EVIDENCE:
- v10 currently has 53 Broad Launch underlying cohorts, 212 account BUYs, 66 SELLs, 146 open positions.
- Current closed Broad Launch evidence is poor: Fast Escape 30 closed / 0 winners / about -187.31U realized; Balanced, Peak Guard and Post-buy Research each 12 closed / 0 winners / about -162.60U realized.
- v9 had a small positive slice for Balanced/Peak/Post-buy (each 8 closed, 2 winners, about +43.44U) but v9 has known accounting/no-route contamination; preserve as benchmark evidence, not as automatically valid champion.
- Therefore newer-version replacement cannot be assumed to be improvement.

HOME PAGE RANKING MUST EXIST:
Current UI hides Top 3 unless a strategy has >=30 terminal outcomes AND complete fresh executable valuation across all open positions. This makes the home page blank even though realized results exist. Correct this.
Provide separate ranking surfaces:
1) REALIZED ROBUSTNESS RANK: always display strategies with terminal outcomes using valid realized Paper accounting. Show independent underlying N, terminal N, wins, median/mean, realized PNL/return, tail metric, top1 concentration and evidence badge.
2) EXECUTABLE EQUITY RANK: only for strategies meeting declared fresh valuation coverage. Show priced/open coverage; missing remains UNKNOWN, never zero.
3) PROVISIONAL BOARD: below-maturity strategies may be descriptively ranked with PROVISIONAL / LOW-N / INCOMPLETE-COVERAGE labels; no promotion authority.
4) CHAMPION BOARD: only promotion-gate winners.
If no Champion exists, homepage still shows Top provisional strategies rather than a blank panel. Never rank zero-sample Flow/Reawakening merely because cash remains 1000U.
The main strategy page lists ALL strategies/lineages, not only the current 12 matrix cards.

VALUATION AVAILABILITY IS A PRODUCT SLO:
- The user is correctly observing many `待可执行报价` and missing strategy executable equity values.
- Current 8790 v10 cut: Fast Escape 23 open / 0 freshly priced; Balanced/Peak/Post-buy each 41 open / only 7 freshly priced. This is unacceptable coverage for a market-grade cockpit even though UNKNOWN semantics are correct.
- Preserve truth: stale/no-route/error/missing must not be faked with DEX price or zero.
- But improve scheduling/coverage so exact or appropriately labelled executable/reliable local estimates arrive quickly; expose freshness and coverage separately.
- Do not let background discovery/observer/Agent work starve held-position valuation or critical SELL.

MEMORY / STORAGE / OOM HARD REQUIREMENTS:
This is now a release constraint for all new strategy, learning, MarketFrame, risk and Web work.
Current project DB is roughly 5.8GB with roughly 888MB WAL and local Python SQLite is 3.51.0. Strategy count and high-frequency risk frames will grow. Do not create an architecture that OOMs or lets storage grow without bound.

Required runtime/resource discipline:
- Keep one bounded writer/runtime architecture unless measurement proves a split is necessary.
- Hot in-memory state only for active candidates/held positions; use bounded ring buffers (1s/3s/5s/15s/60s etc.), bounded dedupe windows and explicit cache caps. Never retain unbounded token/event histories in Python lists/dicts.
- Every queue has a max size, priority/backpressure policy and dropped/deferred counter; held RED/DEAD/SELL work cannot be displaced by bulk discovery/history/UI work.
- Stream/process DB rows in pages/chunks; never `fetchall()` unbounded tables or build giant JSON arrays for Web/reporting. Add LIMIT/cursor pagination and materialized current projections for hot dashboards.
- Web endpoints must use bounded queries, summaries/materialized snapshots and pagination; never load the 5.8GB operational history to render a page.
- Shared token/cohort MarketFrame/RPC/Jupiter/Agent results are referenced by strategies, not duplicated N times as strategy count grows.
- Persist full raw high-frequency events only when decision/risk/gap evidence requires it. Otherwise keep aggregate counters/bounded operational rows or optional compressed cold archive on E:.
- Decision/fill/terminal evidence remains immutable; retention may compact only non-decision raw telemetry under a versioned manifest.
- SQLite transactions remain short; never await network/Agent while holding a transaction/lock.
- Measure and expose DB bytes, WAL bytes, WAL checkpoint latency, active readers, write latency, hot-table row growth, Runtime RSS/private memory, queue sizes, cache sizes and Web response time.
- Define warning/high-water/emergency memory thresholds relative to machine capacity. At high-water: stop/defer low-priority enrichment/Agent/history aggregation, shrink/release reconstructable caches and protect execution/risk. At emergency: preserve state/checkpoint and perform controlled Runtime recovery rather than allowing OS OOM kill/data corruption.
- Agent subprocesses remain bounded and must release memory after completion. No unlimited parallel/subprocess accumulation.
- Large analytics run against bounded/read-only snapshots/copies, not the hot writer connection.
- Complete Online Backup + restore drill and upgrade SQLite to the already-approved fixed version/backport before destructive WAL maintenance. Do not blindly VACUUM/TRUNCATE the active DB.
- Storage retention/compaction must report before/after bytes and preserve references/checksums.

RESOURCE ACCEPTANCE FOR EACH SUBSTANTIAL RELEASE:
- No material unbounded collection/query/cache introduced.
- Runtime memory reaches a stable plateau in a bounded observation window under normal load; no monotonic leak pattern.
- Queue/backpressure and critical SELL priority visible.
- Web state response remains bounded as DB history grows.
- DB/WAL growth rate and checkpoint health are reported.
- No OOM, no data loss, no long DB lock during the controlled deployment check.

EXECUTION ORDER:
Do NOT use this correction to delay the already-identified core P0. Order remains:
1. v11 independent-cash activation / v10 stop frontier.
2. stop confounded Stage4-v2 new enrollment.
3. actual-Fill PositionEquityFrame + all-current-position RiskKernel + critical SELL.
4. restore nonblank truthful ranking + open-ended Strategy Registry/Baseline-12 lineage.
5. valuation-coverage/latency SLO plus Flow/Reawakening input denominators.
6. continue challengers/learning, execution truth, storage hardening and Cockpit.
Resource/OOM constraints apply to every step immediately.

NEXT_SYNC_EVENT: Codex ACK/RESULT for parent task; v11 activation; first resource telemetry snapshot; homepage ranking correction; or a concrete resource blocker.