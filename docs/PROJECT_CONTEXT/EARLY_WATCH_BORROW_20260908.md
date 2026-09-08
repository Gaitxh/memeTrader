# Early watch capacity borrowing — 2026-09-08

Request: `C2C-20260908-EARLY-WATCH-BORROW-20`.

## Finding and bounded change

Independent code inspection confirmed a coverage constraint in `Runtime._remember_pattern_quotes`: both admission and routine rebuilding enforced an isolated early cap of three, even if the chain's growth/mature reservations were unused. The shared market follow-up first becomes due at pool age 901 seconds or later, at least 60 seconds after scheduling, with at most two follow-up targets; it does not provide equivalent first-150-second coverage. The case-specific missing-frame counts supplied in message20 were not independently recomputed in this engineering task.

The change retains a total of ten non-held watches per chain and base reservations early/growth/mature = 3/4/3. Only fresh, usable early candidates can borrow unused capacity after the existing unusable same-slot replacement check. A later underfilled base bucket can reclaim the newest non-held item from an over-base bucket, deterministically. Base reservations are retained first during rebuilding; unused early overflow then survives within ten. Held watches remain outside the quota and cannot be capacity victims. Quote updates do not renew TTL; aging, expiry, unusable-slot replacement, original-pool identity and freshness validation remain in place.

Only the existing watch-selection path and its existing KV telemetry were changed. Added fields report cumulative borrow/reclaim counts and non-held counts by chain/bucket. There is no new scheduler, API source or polling path; the 15-second observer cadence, low-priority gate, held/SELL priority and request ceilings remain unchanged. More of the existing candidate budget may actually be used. Strategy definitions, entry/exit thresholds, accounts, funding and execution settings were not edited.

## Validation

- Five focused watch cases passed: unused-capacity borrowing, empty rebuild continuity, deterministic base-reservation reclaim, per-chain total bound, held/TTL preservation and existing invalid-slot replacement with missing/zero/below-floor liquidity.
- Eight parametrized adjacent cases passed: shared quote reuse, exact receipt provenance, held reuse, mature expiry, surface cache, passive cohort handling and bounded Gecko overflow.
- Independent read-only review found no reachable reservation, capacity, held or TTL counterexample in the changed method. `git diff --check` passed for the two changed source/test files.
- The first watch-test run failed because fixtures omitted the existing liquidity validity requirement and used an incorrect mature-age boundary. Those fixtures were corrected; only `pytest_watch_fixed.txt` and `pytest_boundaries.txt` are passing evidence. The failed `pytest_watch_tests.txt` remains preserved.

Evidence directory: `E:/memeTrader/data/research/early_watch_borrow_20260908/`. The runtime was inspected through the three existing HTTP endpoints and SQLite `mode=ro`/`query_only`, without constructing a Store or running migrations for research.

## Deployment and acceptance

One authorized Paper restart loaded the change at 2026-09-08T13:42:04Z (21:42:04 Beijing), using `scripts/run_paper.ps1`: supervisor 34404 → 40556, runtime 31436 → 40916. The existing Web service was left running. This was a code deployment, not a periodic-restart workaround or account initialization.

The first post-start snapshot at 13:42:48Z showed 17 natural borrow admissions, 10 reservation reclaims and four unusable-slot replacements. Robinhood had early9/growth1/mature0; BSC and Solana each had 3/4/3. All three totals were ten. All five contract/funding/registration table summaries matched their pre-restart hashes (284 additions, 20 v6 activations, 25 registrations, one Paper funding activation, zero fixed-funding restorations). The current period remained `chain-meme-trader/funding-20260906-v002-final-1000`; Paper and Live=false were retained. Process-local passive drops were zero and persisted historical drops remained 56704 batches / 462180 quotes.

The acceptance snapshot completed at **2026-09-08T13:44:27.884884Z**, 143.74 seconds after the restart. `/health` reported running/ok, `/api/live` running, and `/api/performance` ok. All five immutable summaries and current execution settings still matched: ordinary notional20U, buy/sell400bps, fee0U, floor1000U, Paper/live locks unchanged. Snapshot/evaluation/trade frontiers advanced 1912525→1913577 / 1108097→1109146 / 504809→504858. This is ordinary forward progress, not evidence of strategy profitability.

The watch snapshot recorded at 13:44:19Z had 17 borrow admissions, 14 reservation reclaims and ten unusable-slot replacements. Robinhood was early5/growth2/mature3; BSC and Solana were each 3/4/3. All non-held totals remained ten. Process-local passive queue: 321 enqueued, 320 processed, one remaining, max depth8/16, zero dropped batches/quotes; historical counters were unchanged.

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| Pattern duration p95 | 6.752s (120 samples) | 7.387s (9 samples) | Small, unequal windows; remains below the 15s cadence, not proof of unchanged long-run tails. |
| Actual pattern interval p95 | 15.326s | 15.203s | No interval or cadence expansion. |
| Held market-loop duration p95 | 4.380s | 2.592s | Changing load/network prevents a causal speed-up claim. |
| Held apply/exit p50 | 24.507ms | 24.806ms | Similar local median. |
| Held apply/exit p95 | 40.171ms | 51.797ms | Tail increased about12ms with held count28→33; short window does not establish a material scheduling regression or a stable gain. |
| Passive queue wait p95 | 2.201s | 2.028s | Zero new drops in the acceptance window. |

Equal-duration held retrieval comparison uses twelve complete 10-second buckets, excluding the latest partial bucket: before13:39:10–13:41:10Z, after13:42:20–13:44:20Z. Per-token-attempt weighted retrieval seconds were BSC1.785→1.327, Robinhood1.563→0.960, Solana0.974→0.705; total attempts1512→2316, zero request-failure attempts in both windows. These count missing original-pool results as attempts and do not mean all pools were covered. BSC coverage gaps2→3 and Robinhood0→1 were present at the final snapshot; the maximum BSC original-pool age remained about18h, and Robinhood had a71.9s gap. This change cannot manufacture missing upstream quotes.

The bounded natural ledger check examined 522 post-frontier pattern rows up to the same cutoff. There were78 valid early frames and25 non-held same-pool/upstream paths; only three paths had repeated observations (three frames each, spanning58.989s, max gap46.310s). **No observed non-held path met span≥60s with every gap≤30s** in this short window. This is post-deployment evidence, not the first150s from token birth/first valid quote. Aggregate borrowing telemetry cannot identify each borrowed token, so per-token continuity improvement remains **INSUFFICIENT_NATURAL_EVIDENCE**. No full early-path or profitable-coverage claim is made.

Disposition: **ACCEPTED_DEPLOYED — bounded engineering behavior verified**, with incomplete natural trajectory evidence and existing source gaps explicitly retained. No higher request cap, reservation violation or clear material held scheduling regression was observed. Passing tests are saved in `pytest_watch_fixed.txt` (5 cases) and `pytest_boundaries.txt` (8 cases); deployment/API/hash/latency/continuity evidence is in `deployment.json`, `before_deploy.json`, `after_start.json`, `after_acceptance.json`, `acceptance_comparison.json`, `natural_continuity.json` and `natural_early_frames.json`.

## Interpretation and limits

This repair makes existing spare observation capacity usable for early candidates. It does not increase the total watch budget, guarantee complete new-token coverage or establish profitable signal discrimination. Natural borrow/reclaim counts are admission events, not unique tokens or trades. Aggregate watch count includes held tokens and must not be compared directly with the non-held cap of thirty across three chains.

The short deployment window cannot establish long-run latency stability, first-150-second coverage for every discovered token, or Alpha. Existing stale original-pool gaps and negative strategy results remain separate issues. The prior rejection of a new <=300-second fixed40/80 arm remains effective; no strategy retuning was performed. Message19 ModeChat liveness/recovery remains deferred and was not started by this engineering acceptance boundary.

## Message21 addendum: broad pre-deployment coverage denominator

Response to `C2C-20260908-EARLY-WATCH-COVERAGE-ADDENDUM-21`. Lead reports active early1705/both63 (RH497/6, SOL944/27, BSC264/30), any-second502, and activity-free3309/both60. These exact counts and the individual case frame counts are **Lead-reported, not independently reproduced**. The qualitative conclusion of broad early-trajectory scarcity is independently supported below. Missing observations are not evidence that a token lacked a price trend, and coverage is not profit.

The independent read-only extraction finished at13:53:54.635874Z using the fixed historical interval **(08:02:59Z, 13:25:00Z]** on2026-09-08. The latter is an explicit approximation of Lead's `~13:25Z`. It examined9425 token candidates and55452 snapshot rows through existing token/observation indexes. This cutoff precedes deployment at13:42:04Z: these are **pre-fix baseline observations, not a post-fix acceptance comparison**. SQLite was opened `mode=ro` and `query_only`; no strategy, Runtime, parameter, account, funding, history or Live writes/restart occurred for message21.

The unit is one token, not one token per provider/pool. A base anchor is the first *available qualifying* snapshot ordered by `(recorded_at,id)` with positive finite price, finite liquidity≥1000U, its recorded pool age in[0,900)s, original-pool address, `observed_at<=ingested_at<=recorded_at<=cutoff`, and observed-to-recorded lag≤15s. Features come only from that snapshot. Checkpoints require the exact token/pool, strictly later observed/available times, positive price and the same clock/lag rule, at inclusive offsets45–75s and105–135s from anchor observation. The main checkpoint count does not add a liquidity floor or require the same upstream; those are separately reported stricter checks. No later winner labels or case whitelist are used.

Two activity interpretations are kept separate: (1) filter the frozen base anchor using buys+sells≥3 OR volume5m≥200U, and (2) choose a later first qualifying active anchor. Re-anchoring may describe a different enrollment rule, but cannot be presented as filtering the same initial cohort. There were97 changed anchors; seven tokens newly gained both checkpoints after that shift. The Lead's63 versus60 is therefore compatible with an anchor change in principle, but its actual cause remains unverified without the exact query/token-anchor list.

| Independent enrollment | Eligible tokens | Any later exact-pool frame in150s | Both checkpoints | Both / eligible | Full135s window: both / mature |
|---|---:|---:|---:|---:|---:|
| Base, no activity restriction | 5152 | 1945 | 54 | 1.048% | 53/5109 =1.037% |
| Activity filter on frozen base anchor | 2845 | 992 | 47 | 1.652% | 46/2833 =1.624% |
| First qualifying active anchor, reselected | 2942 | 1038 | 60 | 2.039% | 59/2930 =2.014% |

All eligible tokens remain in the main denominator, including missing paths and right-censored windows. Full135s and full150s denominator counts happened to coincide at this cutoff; unfinished windows are explicitly separated rather than silently removed.

| Chain | Frozen-base activity: both / eligible | Reselected activity: both / eligible |
|---|---:|---:|
| BSC | 16/269 =5.948% | 25/322 =7.764% |
| Robinhood | 3/1477 =0.203% | 4/1502 =0.266% |
| Solana | 28/1099 =2.548% | 31/1118 =2.773% |

The fixed-base activity group has only15 same-upstream dual-checkpoint tokens (versus47 pool-only), and39 with both checkpoint liquidities≥1000U. Reselected activity has26 same-upstream and50 floor-eligible (versus60 pool-only). Thus pool-only sparse coverage is already a weak lower-quality description for mechanisms needing consistent upstream measurements. Raw primary-key checks of1267 distinct referenced frames passed identity, clocks/window and anchor floor/age validation. The frozen-anchor subset count assertion also passed; no production test suite or repeated runtime deployment was needed for this report-only addition.

**Disposition:** retain message20's bounded borrowing/reservation implementation and engineering acceptance; independently confirm a broad coverage problem, while keeping **exact Lead1705/63 and3309/60 unreproduced**. Different first-frame selection, source/lag rules or the approximate cutoff could affect comparison, but no specific explanation for the denominator discrepancy is established. No request-cap expansion, new strategy, timing relaxation, retune or restart follows from this addendum. Post-fix first150s coverage and profitable coverage improvement remain unproven.

Reproduction/evidence: `data/research/early_watch_borrow_20260908/addendum21_coverage.py`, `addendum21_run.txt`, and `addendum21/{summary.json,tokens.json,validation.json,lead_message21_claims.json}`. The token artifact includes each anchor and actual checkpoint snapshot IDs, allowing exact reconciliation with a future supplied Lead query without reinterpreting historical evidence.

## Message22: conditional capacity bound and deferred stage2

`C2C-20260908-EARLY-WATCH-CAPACITY-BOUND-22` is recorded as **LIMITATION / CONDITIONAL_BACKLOG / NOT_STARTED**. Message20 remains the sole implemented variable: fixed-total borrowing with base reservations. No second watch-lifetime/rotation behavior is merged with it.

Lead's arrivals944 SOL /497 RH /264 BSC over approximately5.4h imply174.8/92.0/48.9 tokens per hour. Arithmetic is consistent, but the underlying Lead counts remain unreproduced as explained in message21. Under the explicit hypothetical assumption that each non-held early admission occupies a slot for a full900 seconds, even ten slots dedicated entirely to early imply a steady turnover of `10*3600/900 =40 admissions/hour/chain`. Initial free capacity adds a one-time burst; growth/mature reservations reduce capacity available to early. This is a conditional capacity model, **not a measured hard bound**: bucket aging, expiry, invalid-slot replacement and transitions into held status can change actual residence time. Under that model all three reported arrival rates exceed40/h, most strongly SOL/RH, so borrowing alone cannot promise complete coverage.

The separately preregistered stage2 hypothesis is that shortening non-held early occupancy to a bounded approximately150-second trajectory collection window, or an explicitly defined evidence-complete rule, may improve early admission/checkpoint coverage within the same request budget. **Activation requires new post-message20 natural evidence of persistent early saturation/poor60–120s coverage.** The predeployment message21 denominator does not satisfy that gate; the short message20 acceptance window does not establish persistence. No new computation, monitor, scheduler or implementation is started by this record.

If that gate is later met, evaluate stage2 separately from borrowing, retaining held protection, existing request ceilings/cadence, causal original-pool observations and all strategy/funding/history/Live boundaries. Approximately150s is a proposed collection horizon, not an activated parameter. Existing growth follow-up is not due before pool age901s and the held lane applies only to actual holdings, so a young non-held token released after150s is **not guaranteed an immediate handoff**; any resulting continuity gap must be assessed before adoption. No extra requests/cap increase is authorized by this addendum; any exception needs separate justification. Reject the hypothesis if bounded release fails to improve valid early coverage or sacrifices required trajectory continuity/held-SELL priority. Stage2 remains not started pending its evidence gate.
