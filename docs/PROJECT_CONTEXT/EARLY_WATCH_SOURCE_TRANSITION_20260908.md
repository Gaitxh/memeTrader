# Source26 and foundation review — verified facts and next design

Disposition: **READ_ONLY_REVIEW_COMPLETE / NO_NEW_IMPLEMENTATION**. Reply to `C2C-20260908-EARLY-SURGE-SOURCE-CORRECTION-26`. The later user asks whether the system foundation can still be optimized. Current runtime retains ef6dd56 behavior. Message25 was implemented, tested, briefly deployed and rolled back before26 arrived; its truthful status remains REJECTED_RUNTIME_GUARD_ROLLED_BACK, now superseded by26's source review. It must not be relabelled NOT_IMPLEMENTED.

## Current operating evidence — 2026-09-09 00:25 Beijing

Snapshot cutoff2026-09-08T16:25:18.917520Z: health running, Paper, Live=false, original funding period. All chains' nonheld reservations are3/4/3, ten per chain. Since process start13261 passive batches arrived,13257 processed,4 pending,0 dropped; queue-wait p95=2.403s. This does not show a renewed passive-drop defect.

| Component | Median | P95 | Implication |
|---|---:|---:|---|
| Held request stage, including its waiting/network time |1.523s|4.442s|Largest direct held-data latency opportunity; upstream and local waiting are not separated by this metric.|
| Held market loop duration |1.954s|5.391s|Configured1s does not equal real1s completion.|
| Local held apply/exit |34.658ms|58.234ms|Smaller than request-stage delay.|
| Entry batch |13.173ms|51.735ms|Main deterministic entry calculation is comparatively short.|
| Pattern observer round |6.038s|8.467s|Material work inside the15s cadence.|
| Per-token pattern projection |71.398ms|120.693ms|A measured local compute/SQLite target before increasing watch count.|

The restored ten-slot baseline also has held request tails around4.44s. Therefore the earlier20-slot trial's rollback establishes that its preregistered acceptance guard failed, **not** that extra slots uniquely caused those tails. A future trial needs comparable load/startup evidence; this review does not relax the previous guard retroactively.

BSC has3 original-pool coverage gaps, maximum local observation age74512.85s (~20.7h). Robinhood/Solana current age maxima1.61/1.44s in this snapshot. Missing original-pool evidence remains a source/identity coverage problem; polling loop speed alone cannot fix it. No missing data was reclassified as a tradable quote or writeoff.

## Frozen source comparison — exact reproduction

Input: `data/research/early_watch_borrow_20260908/addendum21/tokens.json`, SHA256 `92328f854368527b435993b91a9f6732daa59737e1fa47643c5199058d66202a`. Historical window08:02:59–13:25:00Z on2026-09-08. Fixed first eligible anchor, then activity filter; no activity re-anchoring. Read-only SQLite checks validated **all2845 anchors and2845 complete follow-up ID sets**, reading35106 bounded token/time-indexed snapshot rows. The statistical computation completed14:54:35Z; it is historical evidence, not a current cohort claim.

| Anchor upstream | Tokens | Any exact-pool follow-up within150s | Both45–75s and105–135s checkpoints | Both with anchor's upstream |
|---|---:|---:|---:|---:|
| DexScreener |77|30|15 (19.48%)|15|
| GeckoTerminal |2768|962|32 (1.16%)|0|

Gecko both checkpoints by chain: BSC15/267, Robinhood1/1460, Solana16/1041. These reproduce Lead26 exactly. Denominators above follow the frozen artifact including its short-censored anchors; the horizon-specific transition table below excludes incomplete horizons explicitly.

All32 Gecko-anchor dual-checkpoint tokens actually have **Dex→Dex at the60/120s checkpoints**. Their anchor is Gecko, so they are not same-source-with-anchor paths. There were904 tokens with another Gecko receipt within150s; first Gecko follow-up median90.027s, p10/p90=88.802/90.838s. This directly matches the90s discovery cadence and explains why repeated Gecko discovery alone misses the paired60/120 windows.

## Gecko anchor to observed Dex continuation

These are delays until the **first locally recorded usable Dex quote**, not measurements of when Dex first indexed a token. Observation gaps can reflect unattempted work, selection, queuing, failures or missing upstream coverage. Tokens and exact original pools are distinguished.

| Chain | Gecko anchors | Later usable Dex by frozen cutoff | Later Dex containing exact pool | Exact-pool Dex within150s / fully elapsed horizons |
|---|---:|---:|---:|---:|
| BSC |267|251|207|23/267|
| Robinhood |1460|52|39|2/1450|
| Solana |1041|607|588|90/1041|
| Total |2768|910|834|115/2758 (4.17%)|

Exact-pool checks also inspected the Dex payload's sibling pools; they did not add another matching original pool beyond the834 primary-pool matches here. Conditional on a later Dex receipt being observed, median delay from local anchor availability is6601.17s (~110min); by chain1757.60s BSC,13304.76s Robinhood and6931.79s Solana. These heavily selected observed-only medians must **not** be presented as typical indexing latency for all tokens.

210 Gecko-anchor tokens already had a usable local Dex receipt before the Gecko first-eligible anchor; all are Solana and202 earliest Dex receipts match the same primary pool. Of the2558 without an earlier local Dex receipt,775 get one later by the cutoff;95/2548 with complete150s horizons get one within150s (3.73%). A blanket rule treating Gecko-origin tokens as unindexed or skipping their Dex requests would misclassify known-covered tokens and could prevent the needed source transition.

1783 Gecko-anchor tokens have no usable Dex snapshot anywhere in the frozen window.434 have a completed Dex hydration exposure returning no usable pair after the anchor;1349 have no completed Dex hydration exposure after the anchor. This is not equivalent to434 proven provider-global unindexed tokens or1349 proven never requested tokens: observer batches lack a complete per-token empty-response ledger, failed/inflight rounds are not completed exposures, and a successful quote requires valid local clocks/price. No completed no-pair hydration result was recorded within150s after these anchors.

## Current code explains an actionable scheduling mismatch

- Gecko discovery already reuses its received market data without another request: `GeckoNewPoolsCollector.poll` normalizes the pool, `_poll_gecko_network` persists it and passes it to `_remember_pattern_quotes`. `_complement_snapshot` retains Gecko provider/receipt provenance. No missing first-frame reuse patch is needed.
- `chain_meme_pattern_observer_once` refreshes nonheld watches only with `_dex_batch_quote`. Same receipt/stale checks prevent legally treating the old Gecko payload as a new frame.
- `_shared_market_followup_schedule` schedules eligible ordinary market follow-ups at `max(now+60s, pool_birth+901s)`, until pool age6h. This deliberately routes early Gecko hydration into a later growth-stage queue, leaving the first60/120s to the small watch lane.
- The current Gecko scheduler is90s; the collector's20s cache TTL is not its polling interval. Hydration runs every5s, at most10 targets per hydration-only cycle, with at most2 lifecycle follow-ups, subject to existing low-priority gates.
- `mark_token_detail_hydration('hydrated')` sets `next_attempt_at=NULL` when the shared schedule is empty. Such rows are excluded from both ordinary pending/no_pair/error hydration and due lifecycle follow-ups. There is no generic30-minute delay for successful Gecko hydration. Null-schedule reasons include invalid/stale evidence, low liquidity, invalid pool age or expired lifetime; this source condition is **not** a proved attribution of all1349 missing completed exposures.
- Repeated Gecko success writes also update shared hydration attempts and scheduling. Whether this postpones a particular pending Dex follow-up needs per-token schedule evidence; this review does not claim a measured count of postponements.

Code references: `src/memetrader/runtime.py` `_complement_snapshot` (~2325), `_poll_gecko_network` (~2592–2709), `_shared_market_followup_schedule` (~2775), hydration selection (~2820–2870), `chain_meme_pattern_observer_once` (~7485); `src/memetrader/store.py` `due_token_detail_hydrations` (~9354), `mark_token_detail_hydration` (~9466). An independent read-only agent checked this path; Codex verified the relevant scheduling and storage source directly.

## Smallest directions worth reviewing — not implemented

1. **Reallocate existing continuation work earlier.** For a fresh eligible Gecko anchor lacking an already-known exact-pool Dex receipt, move one already-planned growth follow-up into an existing hydration batch near the early checkpoint. Replace the old planned task, rather than adding a second task. Preserve held priority and batch/request counts. The current two-followup allocation may still starve new tokens; feasible scheduling and displaced growth coverage must be assessed before changing it. This is the highest-value source-transition hypothesis, not a proven zero-cost change.
2. **Separate “market data received” from “Dex continuation observed” using available provenance.** Avoid deciding completion from generic `hydrated` alone. No new schema or retries are authorized here; first distinguish valid scheduled, explicit no-pair/error, and missing/unknown cases. Do not blindly skip Dex by Gecko origin.
3. **Reduce measured pattern-projection work before expanding coverage.** `Store.observe_chain_meme_pattern` reads up to80 history rows over20min per observation, extracts JSON fields and constructs features under the shared Store lock. The120.7ms per-token p95 includes this larger method; it does not separately prove which SQL or parser dominates. Profile this measured path, then consider bounded reuse of parsed history/point-in-time features keyed by token/pool/upstream/frontier, preserving append-only evidence and decision clocks. No cache or index change was made.
4. **Improve exact-pool recovery within existing held priority/budgets.** Existing Gecko pool client and complementary lane only serve eligible held original-pool gaps. Generalizing them to nonheld discovery would create requests/cache misses and requires separate review. Current new-pool frames matching held original pools are already reused; do not implement duplicate polling.

The next coherent design should first address source-transition scheduling and measured projection cost, while preserving the effective original-pool floor and causal timing. An extra address fits a batch but still adds response parsing, history lookup and strategy work. Nothing here certifies Alpha, guaranteed speed or profit.

## Artifacts, controls and chat continuity

Research artifacts: `source26_analysis.py`, `source26_summary.json`, `source26_tokens.json`, `source26_decomposition.json`, `source26_run.txt` under `data/research/early_watch_borrow_20260908/`. Current runtime snapshot: `foundation_20260909_now.json`. Historical cohort/hash/reference validations passed; no runtime test suite was required for this read-only report. No production code/configuration, database, strategy, funding or Live change and no restart in this review.

The user separately requested ending the current Lead chat and creating a new GXH Project chat. The supported node/browser controller probe failed again with `failed to write kernel assets: path not found (os error 3)`. No stop/send/create/rebind was performed. Latest handoff pointers are updated to this review; old routing remains until a supported new-chat creation, model/reasoning verification and E: L0 readback succeed. This tooling blocker does not prevent local research.
