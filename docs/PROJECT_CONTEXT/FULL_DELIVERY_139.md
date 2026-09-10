# Full attachment implementation — 2026-09-10

Scope: user attachment `4e058972-73af-429b-a088-3e506561c877/pasted-text.txt`, and explicit “实现其中的所有内容”. Continuation of138, not a replacement writer or reset. Stages below distinguish source, tests, load and natural evidence.

## Native current-period lifecycle

Existing af7f444 native current-period cash/position/BUY/held SELL/valuation bridge is loaded. A natural native BUY exists at cohort94747 (07:37:33Z). The missing current-period held scheduler was fixed and loaded in6598390. Its max-hold intent is persisted at08:10:43Z even when a current sell quote is unavailable. One bounded current public quote read returned `LOCAL_NO_DIRECT_CAPACITY / insufficient_real_quote_reserves`; no sell output, fill or writeoff has been fabricated. Native exit diagnostics now expose this separately from the legacy held-account monitor. Pons provenance remains DATA_BLOCKED. No repeated successful Pump proof probes.

## Shared Dex trajectory and funded prospective hypotheses

`dex_trajectory.py` computes one bounded exact-pool vector per fresh independent Dex receipt. 512 pools,192 retained frames/pool,310-second rolling paths,900-second cache expiry.5/15/30/60/180/300-second windows use actual endpoints; gaps above30seconds reset continuity and signals. Missing fields/windows stay unknown. Same-valued later observations are valid quiet evidence, not deduplicated away. Solana identity remains case-sensitive through the existing canonical path. No new market requests, polling frequency, watch capacity or provider budget.

Vector: price/log velocity/acceleration, volatility, drawdown/path efficiency, liquidity growth/retention, rolling volume/transaction changes, age-normalized current/hour rates, count-buy share, reported average-notional proxy, turnover/liquidity, FDV/liquidity, R²/residual/monotonic/plateau/jump descriptors and first-dip recovery. Shape alone is not a scam veto. Dex count/volume aggregates do not expose signed USD or independent wallet breadth; those remain unknown here. Official field reference: https://docs.dexscreener.com/api/reference (read2026-09-10).

New distinct5U/max2 arms: `dex_hot_impulse_v1`, `dex_quiet_acceleration_v1`, `dex_volume_leads_price_v1`, `dex_compression_breakout_v1`, `dex_first_dip_resilience_v1`. Existing `liquidity_leads_price_v1` is reused, not duplicated. Frozen rule text lives in policy `trajectory_rules`; no historical threshold search or reuse of failed old fixed-count/price variants. The local rank is only fresh same-chain/age-band observed peers, not all-market ranking.

Three same-hot-signal5U/max2 exit treatments: `dex_profit_velocity_exit_v1`, `dex_liquidity_divergence_exit_v1`, `dex_blowoff_exit_v1`. All retain the same15-minute maximum hold as hot control, existing−20% hard stop/+30% activation/15% trailing. The only difference is the new causal decay trigger. It uses a fresh30-second path entirely after entry, and ordinary strictly-later same-pool settlement. No fixed TP, narrative extension, or parent policy change. Existing dynamic principal/half-runner experiments remain independent and unchanged.

All eight register at a new frontier in the current period via existing additions, common safety, persistent decision claim and next-observation BUY. A safety wait cannot cross a trajectory gap and consume the old signal. Source/tests are not an Alpha claim.

## Diagnostics, Agent admission and UI

Bounded `CohortFlow` records unique admitted common-market cohorts, safety WAIT/REJECT/authorization, BUY and actual partial/terminal receipts, plus per-arm counts and startup30m/steady admission windows.2048 members/6hTTL/32examples; evictions and unlinked receipts are explicit. It does not invent the missing discovery→signal association or count native/legacy paths as common-market coverage. Rediscovery94 and Dex feature denominators remain separately labelled.

Process-start manifest records effective arm IDs and source hashes. UI separates registered, startup-loaded and natural positions, renders exact rule explanations and native unavailable-exit reasons. Performance API reads five existing KV keys only, no history scan.

Narrative observer additionally consumes existing indexed first-party exact-CA listing receipts, at most one early Scout and one later verification within the unchanged3-checkpoint/4dailycall/token budgets. Current healthy exact pool and safety remain mandatory. This is research admission only: confirmed independent diffusion plus actual settled principal recovery remains mandatory for any extension. Metadata/social fanout never becomes confirmation. Queries use existing exact token/pool/kind index,8-row bound,60-second per-case refresh. No new Agent framework, timer or network source.

## Validation and rollout boundary

Closest Python tests for native execution, Dex producer→Store safety→later BUY→hard-stop SELL, gap/dedup, narrative admission, existing rediscovery membership and explainability passed. Frontend strategy test passed. No ordinary accounting or historical policy rewrite. Feature exit treatments use equal-entry/equal-horizon control. Native clock/fee/cap proof fixtures were reused rather than reprobed.

Before load: `data/research/full_delivery139/before.json`. Current period remains funding-20260906-v002-final-1000. Held-fetch p95=2.073s, held-apply p95=.0439s, flat p95=5.407s, passive drops0. These are current mixed-workload measurements, not a controlled speedup result. Existing registration/addition rows and funding records are captured for equality comparison after append-only load. Natural signal/BUY/SELL counts and guards are to be appended after actual load.

## Remaining full-scope acceptance

Use saved16+23 cases/matched controls for remaining causal decision receipts and honest endpoint UNKNOWN; do not redo matching or manufacture6h coverage. Runtime continuation and new trajectory readiness need prospective samples. Agent natural quality remains conditional on useful sources. A fresh external Chat/Project/model/memory validation remains explicitly unverified and nonblocking for trading. Storage120 is DONE: no deletion repeat. Keep all original failure lessons and later126/133 governance corrections; no withdrawn unsigned114 or15m-breakeven90A revival.

## Actual load and saved-case receipt completion

4c7ca9f loaded08:35:54Z; eight arms activated08:35:45Z. API returns startup source hashes and279 effective policies. The first natural read exposed2672 discarded trajectory frames: legacy Dex objects leave ingested_at empty until Store insertion. Fixed the actual producer to use its already-recorded passive queue admission receipt (never current-time reconstruction), explicitly labelled `passive_queue_receipt`. Actual Runtime→Engine fixture passes for that legacy object shape. No provider/clock freshness relaxation.

`scripts/report_righttail_receipts139.py` completed saved47 attribution with read-only indexed per-token evaluation/cohort reads and7468 PK-only saved-snapshot lookups, in5.3s. The frozen cutoff remains2019801/2026-09-08T20:34:35Z; no rematch, snapshot-range scan or new historical trading signal. Output `data/research/full_delivery139/righttail_receipts.json`:16cases+51control-anchor rows (50case-normalized distinct controls). Case dispositions:8 actual decisions,4 ready without decision,2 no exact-pool evaluation in frozen current-funded-period scope,2 no valid anchor. Qualified sampled5/15/30/60/360-minute endpoints across retained rows:21/13/15/8/0. These are price observations with4%/4% proxy, not fills or proof that no earlier stop/floor occurred. No6h precision/profitability claim is possible. Today23 existing summary preserved separately:21found/2missing; no new winner-fit or refreshed matching.

## Final source, load and natural boundary

Trading source `ca358bccbf3fe11c40d5e312ed040818b001b296` is loaded from08:41:26Z. Runtime-start manifest source hashes matched the local runtime/store/native/cohort/Dex/safety/microstructure files. All eight additions are forward-enabled;279 effective policies and45 forward-enabled families. Web-only `916aec5` adds native protocol explanations, Chinese trajectory names and actual per-status safety receipt counts; only the web process was reloaded. It does not reload or pause Paper.

At08:51:22Z, the trajectory engine had5995 independent frames/184 exact pools,133 honest gap resets and3298 rejected/unknown inputs. Natural frozen signals: compression2, volume-leads2, quiet1. New arms had four actual BUYs across three unique tokens: compression2, volume-leads1, quiet1. The second volume signal expired without the required security/next-frame completion. Hot/first-dip/three hot-exit variants had no natural BUY yet; do not loosen their gates. This is engineering/natural supply acceptance, not profitability evidence.

The common-market funnel recorded6 unique admitted cohorts,6 WAIT_SECURITY,6 CHECKED_UNKNOWN,5 authorized and5 BUY cohorts,1 expiry. The six restored age-rate parent/control/derivative accounts sharing one opportunity do not count as six independent signals. Counts for different safety states overlap over time and must not be added. Native and unlinked pre-admission paths remain explicitly outside this common-cohort denominator.

| Measurement | Before139 | At08:51:22Z |
|---|---:|---:|
| held_fetch p95 |2.073s|1.944s|
| held_apply_exit p95 |.0439s|.0343s|
| cohort_passive_compute p95 |1.009s|.925s|
| flat task duration p95 |5.407s|5.204s|
| passive queue wait p95 |2.294s|2.485s|
| passive dropped quotes |0|0|

Current held-fetch failure count1 versus2 in the pre-load snapshot; not zero. Current exact original-pool source gaps/native reserve failure remain distinct from latency. Dex PoolTimeout0/connect errors0, generation1/retirements0, high-priority waiters0. Flat actual start p95=5.463s and pattern observer p95=15.741s; configured5s/15s unchanged. Early cold-start p95 peaks settled, so the latest window passes the existing latency guard. Loads/held populations differ; these are observed bounded windows, not a causal speedup estimate or a new29-minute long-run claim. No wider concurrency or API budget was introduced.

`after.json` verifies exact equality of prior policy-addition rows, current registration and funding records. Eight additions are the only new policy rows. Funding remains `chain-meme-trader/funding-20260906-v002-final-1000`; Paper-only/Live locked. Naturally arriving positions/trades are retained, not expected to stay flat during a live comparison.

## Full attachment disposition

| Scope | Actual implementation / acceptance |
|---|---|
| Shared Dex vector and distinct real entry/exit hypotheses | Implemented/tested/registered/loaded; natural signals and four BUYs above. Existing liquidity-leading mechanism reused. Missing horizons and signed wallet flow not invented. |
| Native supported SOL lifecycle | Real cash assembler/common ledger/BUY/held remaining-raw SELL/migration/valuation code loaded. One natural BUY94747. Current reserve-capacity failure blocks its SELL; max-hold intent persists and value remains UNKNOWN. Pons provenance/unsupported quote classes remain DATA_BLOCKED. |
| Organic/synthetic/clone/event/router mechanisms136–138 | Existing source/producers/safety/strict-next/exit and no-reentry fixes loaded, not reimplemented. Synthetic conditional exact-sell proof still required; ordinary flow does not guarantee safety or profit. |
| Shared funnel / startup-vs-steady diagnosis | Actual in-process cohort stage counters, per-arm attribution, startup/steady windows, explicit missing association; no account-fanout denominator. The current process has not yet reached the30-minute steady bucket. |
| Agent research / hold overlay | Existing two-slot Scout/Verifier, context slimming, persisted-lead progression and recovered-value gate retained. New bounded authoritative-listing early research trigger tested/loaded. No forced Agent call or claim of a new natural verified narrative. |
| Historical16/23 / controls | Prior matching/descriptions reused; saved strict receipt and qualified horizon readback completed. No6h observed denominator in this frozen set, hence no precision/Alpha claim or fabricated discrimination result. |
| Governance / safety / UI | Restored126/133 controls preserved; shared scam/scope safety inherited. Chinese exact rules, registered/loaded/natural distinction, per-status safety and native-exit limitation rendered. |
| Measured efficiency | Shared once-per-receipt features, bounded no-I/O hot path, existing flat/cancellation/fanout repairs retained; bounded current measurements above. No extra requests/forced trades/full historical scans. |
| Continuity / ModeChat | Existing source/tests/install retained. Revision13 packet and TASKS consistent, exact session/lease unchanged. Fresh Project browser opened but initial/readAX both timed out30s; no page evidence, new Chat/model/memory/Lead remain UNVERIFIED. No repeated pairing setup, hook changes, cleanup or topology mutation. |

Revision13 digest: `64c94f39db2bea6c28aa6c1c86c49aa563e9d8dd37ddc48e1c9fc41d7a620ebf`; local resume confirms `CONSISTENT`, owner Codex epoch0 and no stop/terminal fences. This is local readback, not external Lead/Project-memory acceptance. Old source-only/native-ledger-missing/process-denied claims in prior reports are historical and superseded by this actual loaded evidence. No further semantic revision is required merely to acknowledge this packet.

### Closing readback08:59:26Z

`final_natural.json` records six natural new-arm positions: quiet1open, volume-leads2open, compression1open/1closed, first-dip1closed. The two realized outcomes are−0.325998U and−1.298419U (sum−1.624417U); no profitability claim. Hot and its three exit treatments still have no natural entry. Actual common BUY→later SELL now has production evidence as well as fixtures. Native94747 remains UNKNOWN_EXIT for the independently reported reserve reason.

Final browser verification sees Chinese entry labels, cohort8→authorization7→BUY7 (includes old same-fill families), and separate native reserve limitation. It also exposed an existing UI-only stale-summary defect: the live strategy table updated but performance/safety summary fetched only on first entry. The visible strategy/system view now refreshes the existing lightweight performance API at most once per30seconds with in-flight dedup; hidden pages make no polling requests. Closest JS test covers once/30s/hidden behavior and passes. No extra market provider request or Paper restart. Web API independently confirms native protocol-specific explanations loaded.
