# Message23 — bounded residency for borrowed early watches

## Current status — message24 supersedes the deployed residency stage

**SUPERSEDED_AFTER_DEPLOYMENT_REVERTED / HOLD_AWAIT_REVISED_DESIGN.** Exact request `C2C-20260908-EARLY-WATCH-ROTATION-REVISION-24` arrived after `f422c08` had already been deployed at14:13:58Z. Therefore message23 cannot truthfully be marked NOT_IMPLEMENTED. Only its runtime/test changes were reversed; both files now exactly match `ef6dd56`. The historical deployment, observations and findings below remain preserved.

One scoped restart through the existing Paper launcher restored message20 behavior at **2026-09-08T14:27:12.3372995Z** (22:27:12 Beijing), supervisor41544/wrapper43956/runtime45800. Six closest regression cases passed. Runtime source SHA256: `c7355bb815e23a433e19d9cfdaee0e2c8724a4b366535c67cfa7447aecd51222`. Base reservations3/4/3, non-held total10/chain, legacy15/15/20-minute TTLs, fixed-total borrowing/reclaim and held protection remain; borrowed-only180s residency and its telemetry are removed.

At **14:27:45.222500Z**, health/live/performance were normal. All five immutable summaries, funding period and execution settings matched before; Paper/Live=false retained. Snapshot/evaluation/trade frontiers advanced1927686→1928189 /1123233→1123735 /505842→505872. Post-restart watch summary at14:27:40Z had the message20 counters, no message23 residency fields, and ten non-held watches per chain. Passive queue51 in/49 processed/2 pending, zero process-local drops; historical56704 batches/462180 quotes unchanged. This approximately33-second rollback check establishes restoration/progress, not sustained speed or coverage improvement.

The before-rollback snapshot at14:26:03Z independently had zero borrowed identities and near-full base reservations (BSC2/4/3, RH3/4/3, SOL3/4/3), consistent with message24's warning that borrowed-only expiry cannot help while no borrowed capacity exists. This is not a reproduction of its exact13:53Z cohort or proof of every missing-trajectory cause. No additional coverage scan or replacement design was executed.

Evidence: `data/research/early_watch_borrow_20260908/rotation24_before.json`, `rotation24_after.json`, `rotation24_deployment.json`, `rotation24_acceptance.json`, `rotation24_pytest.txt`. Await Lead's revised design; do not automatically implement message22/23 rotation, reallocate reservations, raise requests/cadence or retune strategies. Funding, historical research/trades and Live remain unchanged; ModeChat19 remains deferred.

## Historical message23 implementation and acceptance (superseded by message24)

Request: `C2C-20260908-EARLY-WATCH-BORROW-ROTATION-23`. This separately authorized stage supersedes message22's deferred approximately150-second proposal only for the specified **180-second borrowed early residency**. It does not shorten the legacy base reservations.

## Evidence and decision

The fixed post-stage1 window is13:42:04.142397Z–14:04:48.797350Z, evaluation frontier≤1115392. After timestamp filtering and deduplicating `(token,pool,upstream,observed_at)`, there were3520 pattern evaluations,3472 distinct market observations and624 early frames across78 tokens. The broader active new-token cohort with a fully elapsed150-second observation horizon had227 tokens:75 with any later exact-pool positive causal snapshot,18 with the45–75s checkpoint,9 with105–135s, and **7/227 (3.08%) with both**. Keeping upstream plus requiring the next observation after the first receipt reduced this to2/227. Base-anchor activity filtering and first-active re-anchoring happened to agree in this window. Lead's earlier47/288 and19/0 are not an exact reproduction target without its precise cutoff/list; do not compare different cutoff cohorts as a before/after experiment.

The heaviest examples do **not** establish borrowed-slot monopolization: SOL7CxJ…6cHP had positions overlapping its50-frame/740.5s path; BSC0xb707…a3d6's41 frames over600.0s were all during actual Paper holdings. A cutoff-only held proxy initially misclassified the latter. Root then classified all624 early frames at their evaluation times using actual position open/close intervals:192 were non-held, and four same-pool/source groups had non-held observations spanning over180s. Examples: SOL8bE…pump24 non-held frames spanning499.2s; BSC0x9e46…777721 spanning296.4s. Such spans can include intervening holdings and do not prove uninterrupted slot residency.

The old telemetry cannot distinguish base from borrowed membership for these tokens. Thus **poor post-stage1 coverage and prolonged non-held resampling are confirmed; specific borrowed-token monopolization is not established**. The source does establish that valid newly borrowed watches previously inherited the same15-minute expiry as base watches. The narrow, explicitly requested residency experiment is accepted on that mechanism and coverage evidence, without claiming that it explains all missing trajectories or will improve profit. Runtime borrowed identities/admission clocks are now exposed in the existing watch summary to make subsequent evidence attributable.

The initial research artifact `rotation23_evidence.json` is superseded by V2: it used evaluation IDs as frame references, included pre-start rows and combined provider/receipt restrictions with the main pool-only count. It is retained as an invalid diagnostic. Authoritative corrected evidence is `rotation23_evidence_v2.json`, supplemented by root's `rotation23_nonheld_sample_check.json` and `rotation23_actual_held_classification.json` in `data/research/early_watch_borrow_20260908/`.

## Isolated implementation

- A genuinely borrowed early admission gets `borrowed_at=current` and expiry exactly180 seconds later. Legacy early base admissions keep15 minutes; growth/mature keep their existing15/20-minute lifetimes. Per-chain non-held total10 and reservations3/4/3 are unchanged.
- Ordinary quote updates never renew either lifetime. Borrow origin/deadline remain fixed across bucket aging; held entries ignore expiry as before and an expired borrow can leave after ceasing to be held.
- An unusable early-slot replacement inherits base versus borrowed class from its victim. Replacing a now-growth candidate follows the original growth admission semantics and receives15 minutes, even if the removed watch had originally been an early borrower; imposing a short lease on this new growth candidate would expand the requested scope.
- Existing expiry cleanup records borrowed expirations. The existing watch KV adds that counter and currently watched borrowed token/pool/admission/expiry/held fields. It adds no polling/requests. Expiration counts measure removals, not proof that a different token filled every freed slot. Ordinary later rediscovery can readmit a token under the existing selection rules; no new blacklist/cooldown was added.
- API cadence/ceilings, low-priority starts, held/SELL priority, base-reservation reclaim, strategy definitions, accounts, funding, execution settings, history and Live remain unchanged. Expiry still takes effect on ordinary watch maintenance, not a new180-second timer or forced trade exit.

## Tests and deployment

Ten focused cases passed once, followed by one additional concrete growth-aging replacement boundary test: **11 distinct targeted cases passed**. Coverage includes base15m versus borrowed180s, no renewal,179/180s expiry/new admission, held preservation and later non-held expiry, invalid replacement class, total10, growth/mature reclaim and held-surface continuity. No full-suite repetition. Logs: `rotation23_pytest.txt`, `rotation23_pytest_growth.txt`.

Read-only independent review raised the growth-replacement inheritance question; root retained normal growth TTL to meet the user’s explicit unchanged-growth rule and added the passing boundary test. No unresolved implementation blocker remains from that review.

One authorized restart through `scripts/run_paper.ps1` loaded the change at **2026-09-08T14:13:58.708518Z** (22:13:58 Beijing), supervisor40556→45168/runtime40916→43736. No account initialization or Web-service restart. Before-deployment snapshot: `rotation23_before_deploy.json`; deployment process/hash record: `rotation23_deployment.json`.

Acceptance completed at **2026-09-08T14:18:10.053466Z**,251.34s after startup. `/health` running/ok, `/api/live` running, `/api/performance` ok. Five immutable table hashes matched exactly:284 policy additions,20 v6 activations,25 registrations,1 Paper funding activation,0 fixed restorations. Period `funding-20260906-v002-final-1000`, Paper/Live=false and execution settings (20U,400/400bps,0U fee,1000U floor) remained unchanged. Snapshot/evaluation/trade frontiers advanced1922331→1924533 /1117885→1120083 /505483→505620.

Natural telemetry showed21 borrow admissions,18 reservation reclaims,11 unusable replacements and **2 borrowed expirations**. Current non-held counts were BSC2/4/3=9, RH3/3/3=9, SOL3/4/3=10. The BSC0x2e418…7777 borrowed watch retained its original14:14:09.409442 admission /14:17:09.409442 expiry and remained present with `held=true` at14:17:59.830156, directly confirming held retention beyond the180s deadline. Three previously observed non-held borrowed watches were absent by this snapshot; expiry and reservation reclaim are distinct counters, so do not call every departure a rotation. No new borrowed admission after expiry was yet recorded in this short window; admission fairness is not established by expiration alone.

Passive queue:568 batches in,566 processed,2 pending,max9/16,zero process-local drops. Persisted historical drops stayed56704 batches/462180 quotes. The post-restart counters are not compared as cumulative rates across different process lifetimes.

| Timing | Before | After | Scope |
|---|---:|---:|---|
| Pattern duration p95 | 7.719s | 7.476s | 118 versus16 samples; both below15s cadence |
| Pattern actual interval p95 | 15.295s | 15.529s | Same configured15s interval |
| Held apply/exit p50 /p95 | 32.361/53.251ms | 35.692/48.167ms |120 rolling samples each |
| Held market-loop p50 /p95 | 1.255/2.542s | 1.212/3.421s | Tail increased; not a uniform speed-up |
| Passive wait p95 | 2.397s | 2.042s | Zero observed new drops |

Equal120s retrieval windows (12 complete10s buckets) were14:09:50–14:11:50Z before and14:16:00–14:18:00Z after. Weighted retrieval seconds per token attempt: BSC0.944→1.072, RH0.705→0.671, SOL1.126→1.107; attempts2371→2228, zero request-failure attempts in both windows. Held-token counts33→32, with a different chain mix. The held-loop p95 increase is retained as a limitation; stable median/local-exit timing, bounded pattern duration and zero drops do not establish a sustained material scheduling regression, but this four-minute acceptance also cannot exclude long-run tails. The code adds no request starts or shared-lock changes. No causal acceleration or globally unchanged performance claim is made. BSC still had two original-pool gaps, maximum age66884s (~18.6h); missing upstream data remains unresolved.

Post-deployment first-seen cohort:134 candidates,21 base-eligible tokens with mature150s windows.21-base/10-active denominators had1 later exact-pool observation and **0 dual checkpoints**; the strict source/receipt view agreed. Of four borrowed identities captured before expiry, the three non-held identities had0 eligible next150s same-pool frames, while the held identity had37 and both checkpoints. These observed identities are not all21 borrowing events. Global cohort horizons start at the first eligible quote; the borrowed-identity diagnostic starts at admission, and includes held-lane observations where labelled. Their outcomes cannot be pooled or attributed solely to rotation.

**Engineering disposition: DEPLOYED / TARGETED_VALIDATION_PASS. Natural coverage-effect disposition: INSUFFICIENT_EVIDENCE, no improvement demonstrated in this tiny sample.** No shortfall has been masked by raising the cap, relaxing causal eligibility or deploying another change. Raw acceptance evidence: `rotation23_after_start.json`, `rotation23_after_acceptance.json` (pre-expiry interim), `rotation23_after_expiry.json`, `rotation23_acceptance_comparison.json`, `rotation23_after_coverage.json`. The request's scoped implementation and validation are complete; further coverage work requires new evidence or instruction.

## Limits

This is a bounded data-acquisition experiment, not an Alpha or trading-threshold claim.180s supplies timing allowance for existing60/120s checkpoints, not guaranteed source coverage. An unheld token leaving this watch has no guaranteed immediate growth-lane handoff before pool age901s. Existing source gaps, sampling contention and base-slot coverage remain possible; the original three base early lifetimes were intentionally retained. Message19 ModeChat liveness remains deferred. If later evidence demonstrates a material held/SELL scheduling regression or reservation violation, revert this residency stage alone while retaining stage1 borrowing and historical observations.
