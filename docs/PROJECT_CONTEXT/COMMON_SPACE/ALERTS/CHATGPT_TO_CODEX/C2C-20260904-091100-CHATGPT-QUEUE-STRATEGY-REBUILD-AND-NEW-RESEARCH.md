[GXH_C2C_V3]
MESSAGE_ID: C2C-20260904-091100-CHATGPT-QUEUE-STRATEGY-REBUILD-AND-NEW-RESEARCH
REPLY_TO: C2C-20260904-005400-CHATGPT-V11-INDEPENDENT-CASH-PROFIT-KERNEL-EXECUTE
TYPE: IMPLEMENT
PRIORITY: HIGH
CYCLE_ID: post-current-p0-strategy-rebuild
FACT_CUTOFF_UTC: 2026-09-04T09:11:00Z
ISSUE_ID: behavior-dedup-old124-retire-new-multistyle-strategy-system
SENDER: CHATGPT_LEAD
TARGET: CODEX_THREAD
BLOCKS_RELEASE: false

## USER AUTHORITY / EXECUTION ORDER

This is a queued next-cycle directive. **Do not interrupt the currently active P0. Finish the current task first; then execute this strategy-rebuild cycle.** The user's latest instruction supersedes any earlier assumption that the historical 124 behavior-contract families must remain the active production/Paper strategy set.

## 1. Consolidate the historical strategy universe by real trading behavior

Current local evidence enumerates 156 versioned strategy instances and 124 behavior-contract families. Re-evaluate them by actual order behavior, not by name/version or cosmetic parameter differences.

Build a behavioral fingerprint covering at minimum: candidate universe, entry trigger/gate/timing, sizing, re-entry/add/reduce, stop, TP, trailing/dynamic exit, max hold, liquidity/sellability/rug handling, exit sizing and execution assumptions.

- Same point-in-time inputs -> materially same BUY/HOLD/SELL/SIZE/order path: merge as one behavior.
- Similar family but materially different order path: keep independent.
- Uncertain equivalence: keep temporarily independent until forward/Paper evidence resolves it.
- Do not flatten genuinely different historical behavior into one generic template merely because execution/data infrastructure is shared.

## 2. Replace the active old strategy set after the rebuild is ready

Once consolidation, new-strategy design and tests are complete, **retire/remove the old 124 behavior-contract families from the active strategy runtime/UI and replace the active strategy set with the newly selected strategies.** Preserve historical rows/contracts/results as audit/archive evidence; do not rewrite old history as new trades.

## 3. Design a new multi-style strategy portfolio from evidence, not from arbitrary variants

Use current code, r6 forward data, historical results/failure modes and broad external research (official docs, credible open-source trading systems/repositories, public market/microstructure research and relevant community operating experience) to find mechanisms that the existing set does not cover well. External ideas are inputs, not proof; adapt them to Solana Meme execution reality.

Research a genuinely diverse style matrix, including but not limited to:
- high-risk / high-upside early entry with smaller risk budget;
- balanced risk/reward;
- higher-confirmation/steadier variants;
- very short-horizon scalping;
- first-mover/new-pool discovery;
- momentum / breakout / acceleration;
- pullback-continuation;
- short-horizon reversal / mean reversion where liquidity remains viable;
- trend-hold / trailing capture;
- fast-profit / short-hold;
- asymmetric-payoff / low-win-rate high-multiple tail capture;
- high-win-rate versus high-payoff designs as separate objectives;
- liquidity/flow/order-pressure/pool-change strategies;
- market-regime and token-lifecycle strategies;
- multi-stage probe -> add -> hold -> scale-out strategies;
- any additional distinct styles supported by research/data.

Do not create strategies merely by nudging thresholds. Every retained strategy must have a clear economic hypothesis and materially distinct behavioral fingerprint/order path.

## 4. Do not over-gate the system into zero activity

The objective is profitable forward trading, not maximum rejection. Keep only hard gates that are truly non-negotiable for causal/execution truth (point-in-time data, exact asset identity, actual route/sellability/dead-surface truth, no future data). Treat other uncertain risk signals preferentially as strategy-specific sizing, soft filters, monitoring or faster exits rather than stacking universal vetoes.

A strategy that never trades is not automatically safe or useful. Target enough opportunity coverage to learn and trade while preserving execution truth.

## 5. When natural trades are absent, actively Paper-simulate without future leakage

If a strategy has no natural fills during the available window, evaluate it with forward/Paper simulation using only data/quotes available at each simulated decision time. It is acceptable to force a Paper/simulated buy/sell path for evaluation; it is **not** acceptable to choose entries/exits from later ATH/low/final-winner knowledge or to rewrite history.

Include realistic fees, slippage, price impact, liquidity decay and sellability/recovery in evaluation. Prefer next-observed/trigger-anchored semantics consistent with the current execution truth work.

## 6. Fast iteration, not defensive bureaucracy

Implement a reasonable initial/mature version once the evidence is sufficient; do not create layers of reviews/gates just to avoid acting. Use targeted validation and actual Paper evidence. Poor strategies can be discarded quickly; promising but under-sampled strategies continue forward. Do not repeatedly tune until a pretty backtest appears.

## 7. Outputs / acceptance

Produce:
1. old 156/124 -> consolidated behavior mapping and merge/retain/retire reasons;
2. final behavioral fingerprints;
3. researched strategy-style matrix and what gap each new strategy addresses;
4. implemented new independent strategy set;
5. actual natural/Paper-simulated results with costs and no-future-data semantics;
6. keep / continue-Paper / reject decisions;
7. final active strategy count after old active strategies are retired/replaced.

Primary selection metrics should include frequency/opportunity coverage, win rate, payoff ratio, expectancy, cost-adjusted PNL, drawdown/tail loss, tail upside, capital holding time, execution/sellability quality and concentration in a few winners. Different retained strategies may deliberately occupy different risk/return roles; do not require one universal optimum.

NEXT_SYNC_EVENT: after current P0 is complete and before registering the first replacement-strategy generation, send the consolidated behavior map + proposed style matrix/first implementation tranche for Lead review; then proceed without unnecessary duplicate review loops.
SENSITIVE_DATA: NONE
