# Message25 — bounded early-surge watch

Request: `C2C-20260908-EARLY-SURGE-WATCH-25`, following rollback24. **Final status: REJECTED_RUNTIME_GUARD_ROLLED_BACK.** The scoped implementation passed targeted tests and briefly ran, then was reverted under the predeclared latency gates. Current runtime is again exact ef6dd56 behavior (restoration source d6757b4).

## Scope and independently verified basis

Current base is the exact ef6dd56 runtime restored by d6757b4. The previous borrowed-only180s experiment was deployed then reverted, not never implemented. At14:32:02Z the current watch had full3/4/3 BSC and SOL reservations and RH5/2/3. Thus spare borrowing alone cannot supply new slots when the legacy ten fill. Earlier corrected coverage evidence already established low first150s coverage; Lead's63/1705,47/288 and19/0 are cutoff-specific claims, not newly reproduced numbers. Historical analyses found some longest paths were held, so these are not blanket evidence of non-held monopolization.

The [DexScreener reference](https://docs.dexscreener.com/api/reference) documents up to30 token addresses per batch. Current collectors.py batches at30 and fresh requests disable429 retries. The observer explicitly excludes held tokens, issues at most one batch per chain per15s round, and yields between local token projections. No new provider or scheduler is required.

Implementation preserves legacy10 and its3/4/3 reservations/15-15-20minute TTLs. Up to ten additional non-held early admissions per chain use a separate surge class with a fixed180s deadline. Surge entries cannot become legacy slots or renew their deadline; held entries ignore expiry as before. Admission is early-only; a watch aging during the180s window retains its fixed deadline rather than acquiring a growth TTL. Invalid replacements retain the appropriate class. Growth/mature reclaim legacy early overflow exactly as before. Only fresh usable candidates may enter overflow.

Two request-count boundaries are necessary: surge-due targets only accompany an already-due legacy batch; a surge-only round sends nothing. Non-held surge entries are excluded from Solana pool/vault resolution, preventing extra RPC work from the new watch identities. Held surge entries retain ordinary held semantics. Existing queue/priority gates, timeout, cadence, strategy rules, accounts, funding and Live remain unchanged.

## Acceptance gates frozen before deployment

Run closest watch, batch-call and held/yield regressions once. Verify unchanged immutable summaries and execution settings, all three APIs and advancing frontiers. Observe an approximately five-minute natural acceptance window, enough for180s expiry and mature first150s cohorts. No scheduled monitoring or research is created.

Reject/revert this stage for any deterministic extra request, provider rejection/429 in the affected lane, new passive drops, pattern duration p95>=12s (80% of its15s cadence), or material held regression (p95 rises>25% and by>20ms for local apply/exit or>250ms for fetch). These are conservative engineering rollback criteria, not trading thresholds. Changing load and network remain limitations; no Alpha or sustained speed claim follows a short pass. Request totals are not globally instrumented: real-HTTP mock call counts establish the batch invariant, affected-lane call/429 counters plus source health provide runtime evidence, not proof of every global HTTP request.

Baseline evidence: `data/research/early_watch_borrow_20260908/surge25_baseline.json` at14:32:08Z. Pattern p95=10.603s (19 samples), held apply/exit p95=57.256ms, held fetch p95=2.228s; zero process-local passive drops. Its health response briefly said stale while contemporaneous source/progress and a later independent live readback were running; recheck at the actual deployment boundary. A current predeployment snapshot and equal300s cohort windows will be used for acceptance. Original-pool gaps are pre-existing and are not repaired by watch capacity.

Coverage is measured at the fixed first causal eligible anchor (price>0, liquidity>=1000, pair age<900s, <=15s record lag; activity filter>=3 buys+sells or volume5m>=200). Require both45–75s and105–135s exact-pool checkpoints, report censored rows and same-source stricter results separately. Follow-up observations may come from held or other lanes; cohort improvement cannot alone be attributed to surge. Ordinary later discovery may readmit an expired token; no new blacklist or fairness claim is added.

## Trial result and rollback — final cutoff14:44:22Z

Thirteen distinct targeted cases passed:9 passed initially, and4 existing assertion cases passed after updating them to check legacy10 continuity while allowing the newly requested surge capacity. Production code required no correction from those failures. Tests cover20 total/chain, base3/4/3 and legacy TTLs, fixed surge expiry/no promotion/held retention, reservation reclaim, invalid replacements, real HttpClient MockTransport one-request batching with held exclusion and zero surge-only requests, no extra nonheld Solana RPC, and yielding to held work. The unchanged restored code's previous6-case rollback validation remains applicable and was not redundantly rerun.

The existing Paper launcher loaded the trial at **14:41:09.2543485Z**, supervisor46616/wrapper41600/runtime46540. Trial source SHA256 `fd23ab8c828bbec93c707cfc2f147330d22b6f8a4d322e4572561cf0f644f532`. At14:42:12Z three APIs were healthy and immutable summaries matched. Existing watch telemetry at14:41:58Z showed17 surge admissions,0 expirations,3 batch calls,0 observed pattern HTTP429s; nonheld counts BSC15,RH19,SOL13. No new provider-error timestamp was recorded during the sampled trial in the API source subset. These are bounded affected-lane measurements, not a complete HTTP error ledger.

| Metric | Before deployment | Trial | Result |
|---|---:|---:|---|
| Pattern duration p95 |10.775s,45 samples|12.623s,3 samples|Above frozen12s guard|
| Held fetch p95 |2.724s,120 samples|4.321s,61 samples|+58.6%,+1.597s; exceeds25%/250ms guard|
| Held apply/exit p95 |65.973ms|44.010ms|No local exit regression observed|
| Passive drops |0 process-local|0 process-local|No new drops|

The guard was triggered early. No warmup exemption or threshold relaxation had been preregistered, so the trial was stopped without waiting for a better sample. The very small pattern sample, startup work and changing network/load **do not establish a causal sustained regression**, but the user explicitly required a conservative rollback. The data do not support claiming20 watches are inherently impossible either. This stage is rejected for current deployment acceptance, not as a proved universal mechanism failure.

Only this stage's runtime/test edits were restored to d6757b4, retaining the full attempted diff in `surge25_attempt.patch` and all observations/trades. One rollback restart through the same launcher at **14:43:03.1713818Z** restored supervisor47868/wrapper44908/runtime36068; source SHA256 `c7355bb815e23a433e19d9cfdaee0e2c8724a4b366535c67cfa7447aecd51222` equals the prior ef6dd56 restoration. These are deployment/rollback restarts, not a periodic-dormancy workaround.

At **14:44:22.104631Z**, health/live/performance were normal; five immutable summaries284 policies/20 activations/25 registrations/1 funding activation/0 fixed restorations matched before and during trial. Original `funding-20260906-v002-final-1000`,20U/400-400bps/0fee/1000floor settings and Paper/Live=false retained. Frontiers before→trial→restored: snapshots1932054→1933219→1933931; evaluations1127592→1128757→1129467; trades506072→506172→506228. Restored watch had10 nonheld per chain and no surge fields. Passive175 in/175 processed/0 pending/0 local drops; historical56704 batches/462180 quotes unchanged. No new strategy/account/funding activation or historical rewrite occurred.

## Natural coverage result and limits

The300-second pretrial window14:33:57.784115–14:38:57.784115Z contained298 first-seen candidates and185 snapshot rows. Fixed first eligible anchors40, including21 with mature150s windows; broad-active25, including14 mature and11 censored. Mature active14 had1 later exact-pool frame,0 paired checkpoints; strict same-source later-frame count0. Chain composition was13 RH and1 SOL, so this tiny window cannot reproduce the earlier multi-hour Lead63/1705 denominator or establish chain-independent rates.

The deployed interval lasted only113.85s before the rollback stop. Its79 first-seen tokens had only1 snapshot row in the bounded query and **no qualifying first anchor**, hence no mature150s coverage denominator. Unanchored identities are reported separately from censored eligible anchors; neither is silently counted as a successful trajectory. Natural180s surge expiry/rotation and150s coverage improvement were **not validated**; the tests establish expiry logic only. The earlier proposed equal300s comparison was aborted by the required runtime guard, not completed with a shortened denominator disguised as equal.

Evidence under `data/research/early_watch_borrow_20260908/`: `surge25_pytest.txt`, `surge25_pytest_legacy.txt`, `surge25_before_deploy.json`, `surge25_deployment.json`, `surge25_after_start.json`, `surge25_rollback_deployment.json`, `surge25_after_rollback.json`, `surge25_acceptance.json`, `surge25_coverage_before.json`, `surge25_coverage_aborted.json`, and the attempted patch. A local speech notification completed after rollback as requested. No automatic retry, further capacity/TTL change or strategy experiment is active. ModeChat19 remains deferred. This report is engineering evidence, with no Alpha/profitability claim.
