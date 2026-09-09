# Background Shadow budget59 — reject direct cadence change

REPLY_TO: C2C-20260909-BACKGROUND-SHADOW-BUDGET-59
DISPOSITION: REJECT_UNSAFE_NONTRADING_ASSUMPTION

At2026-09-09T04:13:00.329262Z, flat task duration p50/p95=5.515/8.576s, actual interval5.799/8.803s, configured5s. Latest100 flat observations:72 insufficient_mature_observation,12 flat_watch,16 mature_observation_no_breakout; no near/candidate in that bounded sample. This does not establish the latest state of every historical token/pool. Hydration p95=5.379s; held_fetch p95=2.700s/failures0, held_apply p95=.04175s. Evidence: data/research/shadow_budget59/performance.json,last100.json.

## Verified hidden consumers

- `runtime.py:7277` flat_compression_breakout_shadow_once calls common `_refresh_chain_meme_market_marks(...observe_flat_breakout=True,high_priority=False)`.
- Common `_dex_batch_quote` calls `_remember_pattern_quotes` in chain-meme mode (`runtime.py:1679`). That sends the returned quotes into the passive cohort batch queue and refreshes shared pattern watches (`runtime.py:7303` onward). This happens before flat-only status recording.
- The refresh applies shared market marks (`runtime.py:7221` onward), wakes `_chain_meme_decision_wakeup`, then records flat state. `store.py:31511` batch application upserts tokens and ordinary shared market marks.
- Flat status itself is observer-only and its table has no direct strategy consumer, but the data-acquisition path is not isolated from trading. Labels decision_eligible=false/affects=none do not disable these shared side effects.

## Existing cadence semantics

`store.py:23578` already selects ordinary tokens only when their market last_attempt_at is at least60s old, and near_trigger/breakout_confirmation_pending/shadow_breakout_candidate at5s. The broad latest-evaluation and latest-observation GROUP BY work still runs every outer iteration. Each iteration returns at most30 due tokens across chains. Changing the whole task to60s would also reduce aggregate batch service capacity and delay the shared passive market stream; it is not merely enforcing an absent per-token timer.

Consequently the requested prerequisite “truly non-trading” is false for this implementation. No cadence/code/threshold/history changes and no restart were made; no post-change metrics or tests are claimed. Held/native hydration remains unchanged. This follows the explicit instruction to report rather than change when hidden consumers make it unsafe.

A separate query-only optimization could preserve exact due-target/network semantics, but needs a measured grouping plan and coherent invalidation (new evaluation, latest pool/state, held changes, attempt times). It must not cache ordinary targets for60s while silently discarding newly known near-trigger state. Such a redesign was not added to this bounded scheduling request.
