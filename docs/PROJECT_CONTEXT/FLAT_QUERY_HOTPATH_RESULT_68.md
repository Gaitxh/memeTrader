# Flat target query68

REPLY_TO: C2C-20260909-FLAT-QUERY-HOTPATH-68
Disposition: REJECT_UNVALIDATED_QUERY_REWRITE_NO_DEPLOY

Profile only target selection, no network/strategy modifications. Current Store query uses existing partial index chain_meme_trader_v6_entry_eval_pool_idx(definition_version,token_id,id DESC) with exact nonempty pair predicate; latest observation uses existing covering observer/token/pair/id index; open exclusion uses partial open-token index. No missing required index demonstrated.

Read-only captured query parameters, exact30 ordered output and EXPLAIN in data/research/flat68/baseline.json. One full current selection measured17.393952s wall time. It was unexpectedly slow; subsequent probes used explicit3–5s SQLite progress-handler deadlines. Plan:latest_eval group coroutine;latest_observation materialization;110k latest row lookups + JSON age/filter;joined token/open/mark/observation lookups;temporary ORDER BY before LIMIT. Component probes:latest_eval110164 groups2.018843s, latest_observation37741groups.267101s. Dominant full-query remainder therefore join/materialization/filter/order across broad latest-token universe, not merely observation GROUP BY. Component timings separate instants/caches, not additive CPU accounting or p95.

Smallest local rewrite tested read-only: replace full latest_observation CTE/materialization with correlated latest observation index lookup for same observer/token/exact pair. Candidate interrupted at5.000741s budget; no completed output/equivalence result or measured p95 improvement. It is NOT claimed slower than17.39s, nor a successful optimization. A single baseline and censored candidate cannot justify deployment. The existing query already operates off event loop via to_thread with independent read-only connection, but still consumes shared I/O/CPU.

No source edits, no index creation/schema migration, no cache/frontier or scheduler change. No runtime restart, funding/reset/Live. All cadence/membership/order/max30/near-trigger and mark/cohort/wakeup side effects remain existing behavior. Production-safe read profiler had no writes; no repeated heavy benchmark to manufacture confidence. No fixture equivalence test for an unselected code change. Deploy acceptance not met, so reject this candidate as required.

Remaining concrete bottleneck:scanning/joining110164 latest evaluated identities to yield30. A maintained latest-target projection would require explicit invalidation/updates on every relevant evaluation,observer,mark and position change; not introduced speculatively in this narrow patch. No negligible-cost or p95 improvement claim. Artifacts baseline.json,candidate.json,components.json are durable; candidate SQL kept only as research evidence.
