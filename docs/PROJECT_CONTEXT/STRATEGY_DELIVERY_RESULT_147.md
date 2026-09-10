# Delivery147 — actual held priority, not the last120 admissions

ACK/RESULT `C2C-20260911-147-HELD-PRIORITY-ROOT-FIX`. Existing root Codex remains the sole production writer and able to continue; no takeover or Agent/ModeChat product expansion.146 is already delivered and is not reimplemented here.

**Source a00452a implemented/tested/pushed and loaded2026-09-10T19:35:48.593302Z, Paper PID34192.** All13 enumerated runtime manifest hashes match current source. The new timing/coverage target fields are naturally published; served app.js exactly matches disk. Only the freshly identified Paper supervisor/children were stopped, then the existing `scripts/start_system.ps1 -NoOpen` / `scripts/run_paper.ps1` restored it. Existing Web8790 was reused. No account initialization, policy addition, history modification or funding change.

## Concrete change and fixed-input proof

Store still examines only the newest120 admitted receipts. It now excludes receipts with a matching version/arm/cohort position, terminal enrollment claim, future/expired decision or missing cohort identity. The deadline uses the registered execution contract, default120s; a longer300s contract is tested at its exact boundary. Valid recent entries carry the cohort's original pool. OPEN positions remain independently eligible regardless of age or same-token rejection. Ready/retry/submitted SELL intents remain eligible despite age; pending BUY uses its actual intent expiry. Existing authenticated Flap successor resolution uses the same injected as-of time and keeps original pool provenance.

Runtime held membership is **OPEN_POSITION only**. Valid recent/pending tokens have a separate priority set and protection, without the held watch-cap exemption. Pattern/flat low-priority requests exclude these current priority tokens. When flat needs the same token, its callback consumes the next actual priority response rather than another request or cached replay. Safety pending, ordinary pending-entry, next-frame and lease protections remain. Existing passive/Store learning callbacks continue; expired trading eligibility does not delete learning episodes or manufacture their endpoints.

The exact frozen production input at **19:25:35.367657Z** contains120 admissions,53 relevant positions,0 pending intents,58 cohorts,96 claims and17 tokens. On that **same** input:

| Item | Before | After |
|---|---:|---:|
| Distinct high-priority targets |17|3|
| Actual OPEN token targets retained |3|3|
| Removed targets backed only by RECENT_DECISION |0|14|
| Eligible RECENT receipt rows |120|0|

All removed tokens were recent-only; no OPEN target disappeared. Receipt exclusions are48 terminal claims,53 existing positions and19 expired/future rows. These are receipt counts, not120 removed tokens. A token with an open position remains even when its recent receipt is excluded. `fixed_comparison.json` contains the exact retained/removed identity+pool table. No market-time comparison is used to establish this target-set reduction.

Bounded production read-only EXPLAIN uses the existing admission status index, position unique/market indexes, cohort primary key, claim cohort index and intent due index. No new index/schema/full-history scan. A single current selector call took50ms; the frozen fixture took40ms, neither is a runtime p95 or general speedup claim.

## Validation and runtime boundary

- New real-Store database test covers rejected/expired/closed/stale/future receipts, exact pool, longer deadline, foreign-arm terminal isolation, old OPEN, SELL and unexpired/expired BUY, unchanged decisions and same-input restart results.
- Runtime tests cover actual held versus pending, pending protected within non-held cap, no duplicate low request, and genuine priority-response delivery to flat.
- Closest pool-identity, timing, held-cooldown/batch and two held/background concurrency checks passed. Two old concurrency fakes were updated to the actual diagnostics/get_kv contract. No production shim was added for incomplete fixtures.
- Node strategy/UI test passed: actual-open/pending/rejected-receipt count labels are distinct. The broader eight legacy reactivation tests selected initially fail on their pre145 missing-get_kv fake; they were not silently claimed passing or used to change production behavior. The current147 pending/cap protection path has its own passing runtime test. No full-suite claim.
- `/health`, `/api/live`, `/api/performance`, `/api/strategy-universe` succeed. At19:38:02Z their read times were.126/3.468/.021/.165s, distinct from market latency. Paper=true, Live locked, funding remains `chain-meme-trader/funding-20260906-v002-final-1000`.
- All25 definition registrations, original319 policy rows,1 funding activation and0 restoration digests equal before. Captured317/318/319/**320** policy rows also compare exactly. No new strategy or cash allocation.

Natural readback **19:38:02Z**, about134s after load: high-priority2 actual OPEN tokens,0 pending;120 excluded recent rows. This later count differs from the frozen3 because positions naturally close. Pending SELL quote count0. The earlier first30s had3 open tokens/3 high-priority targets.

| Metric | Before19:32:14Z | After19:38:02Z |
|---|---:|---:|
| Actual positions / distinct held |4 /3|see captured API; priority OPEN2|
| held_fetch p50 /p95 |1.021 /2.892s, n120|.607 /2.432s, n93|
| held_apply_exit p95 |47.44ms|26.17ms|
| passive queue wait p95 |2.278s|2.663s|
| passive compute p95 |1.550s|1.002s|
| low observer fetch p95 |6.656s|4.642s|
| flat selection p95 |.947s,n120|17.307s,n15|
| passive dropped batches/quotes |0/0|0/0|

The short held window does not regress; queue wait increased and the cold flat-frontier selection sample is elevated. Do **not** claim sustained/system-wide causal acceleration. Dex PoolTimeout/connect errors0, active generation1/no retired clients, low/high waiters0 at this cutoff. No concurrency, API cadence, watch capacity or source-budget increase. C3 extra batching stays disabled.

Shared observation still advances: persisted passive learning callbacks24992→28808 and labels26→30; horizon counts26→27 OBSERVED and63→92 UNKNOWN. Coverage30s OBSERVED61→65,120s69→76,300s51→51. This includes intervening natural time/restart and is continuity evidence, **not** a matched coverage-gain estimate. Every non-held chain remains capped10 with the existing reservations/leases; no dedicated high-frequency learning fetch was created. Missing samples stay UNKNOWN.

## Remaining nonAgent scope, without restarting completed work

| Status | Scope |
|---|---|
| IMPLEMENTED_LOADED | Existing supported native143 and derived/strategy139–144;145 two source-faithful trend seeds/restricted recipe path;146 causal model fixes and independent320;147 priority/identity separation. See their existing reports; no repeated native residual or case scan. |
| WAIT_NATURAL_EVIDENCE | Learned model releases/rollback, recipe append/economic support, actual extended-hold treatment, sustained resource guard and controlled2/3-frame/30/120/300 coverage improvement. Registered/trading does not establish profitable learning. |
| WAIT_PREREQUISITE | Existing conditional C3 extra-batch budget; remains disabled. |
| EXTERNAL_BLOCKED | Pons provenance and unsupported native quote classes; frozen saved cases without qualified6h endpoints. No fabricated execution or historical backfill. |
| DEFERRED_BY_USER | Agent restoration, new browser/ModeChat product expansion and old-chat recovery. These do not block current deterministic Paper. |

Evidence is bounded under `data/research/held_priority147/`: frozen.sqlite3/fixed_input/fixed_comparison/live_query, before/after_start/accepted/start_checks/accepted_checks and reload_tree. This research snapshot is an input fixture, not a recovery backup or production replay.

**Final short guard19:40:07Z (259s after load):** same PID34192,5 open positions/3 unique held, high-priority3 actual OPEN/0 pending, pending exit quotes0. Held_fetch p95 **1.856s/n120** versus pre2.892s/n120; apply29.71ms, passive compute1.055s, queue wait2.473s versus2.278s, drops0, PoolTimeout0/connect0 and zero high/low waiters. Flat selection p95 settled to.783s/n39 after its cold sample; no flat selector source change. Coverage120s observed83 and30s65 continue;300s remains51. This meets the short held/resource guard, not long-run causal coverage/profit proof. All old digests and captured317–320 policies still identical. DB36,331,282,432→36,352,565,248 bytes (+21,282,816), WAL771,482,392 unchanged; whole-system growth is not attributed to147. Exact final API data: `data/research/held_priority147/final.json`.

Local continuity checkpoint25, digest `58a1167c5d8728d369a149ad1d80bbb246dc554467e679b2760e5dd15d044777`, resume CONSISTENT; sole codex lease epoch0/no fences. CURRENT_TASK/HANDOFF updated once. This does not verify fresh Chat/Project memory or transfer ownership.
