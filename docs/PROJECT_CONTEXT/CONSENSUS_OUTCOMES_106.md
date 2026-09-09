# CURRENT DISPOSITION: IMPLEMENTED_UNARMED_RUNTIME_GUARD_FAILED

25d1059 removes production collector initialization after19:54:05Z guard: heldfetchp957.305s vs2.715 before, pattern19.959 vs6.204; apply.048s, passive drops0, DexPoolTimeout/connect0. No prospective consensus rows/pending work; correlation does NOT prove this empty collector caused latency. Nevertheless trial was not accepted. No repeated restart workaround; one scoped rollback load. Exact implementation remains testable/unfunded but outcomes are currently NOT collected. Re-enable only after latency cause/valid comparable baseline is resolved; no automatic retry or historical reconstruction. Source7 tests plus final unarmed-registration fixturePASS. Pump105 UNKNOWN classification remains loaded.

# Consensus passive outcomes106
REPLY_TO: C2C-20260909-CONSENSUS-OUTCOME-106

Code41a3849 committed/pushed and loaded through existing Paper launcher2026-09-09T19:50:53Z. Research only, no funded policy/account or provider request. This load also includes Pump105 UNKNOWN-classification correction e49e532; it does not complete native V2 execution math.

## Contract
Each newly inserted clone_consensus_leader_v2_shadow evidence starts one outcome at its selected strict-next original-pool frame. Existing unique(definition_version,kind,source_key) insertion is the durable decision-key boundary: duplicate callbacks, cycles/restart cannot capture another row. Newly inserted capture and pending KV persist in the existing evidence transaction. Historical evidence is never seeded. No reliance on bounded seen memory as sole dedup.

Store.add_snapshot callback consumes naturally persisted later exact-pool snapshots only. SOL case preserved/EVM canonicalized. Three clocks must order observed<=ingested<=recorded, receipt lag<=30s; each accepted observation must strictly follow previous accepted recorded time. Horizons15/60/240m from selected frame observed time take the first floor-valid causal frame at/after horizon within fixed5m grace; recorded availability must also fit. No nearest-future hindsight selection/MFE/ATH or alternate-pool stitching. Missing/invalid/future observations remain UNKNOWN; after horizon+5m expire UNKNOWN. Invalid anchors count in denominator but cannot resolve. Freeze current4%/4% and additional per-fill-cost/floor proxy; 5U reference, no actual BUY.

Each outcome has raw/cost-estimated return/provider/three clocks. First explicit original-pool liquidity<1000 observation persists separately from first costed-positive sampled observation; report FLOOR_FIRST/POSITIVE_FIRST orUNKNOWN at horizon. Later recovery cannot erase floor-first hazard. No assumption that gaps were safe or that a below-floor snapshot proves permanent death. These are price proxies, never executable sellability/strategy exit replay. All inter-sample path coverage remainsUNKNOWN.

Reuse safety Shadow bounded machinery only; its live behavior unchanged. Pending128, recent128, seen512, reason groups256; overflow increments capacity_skipped, not silent coverage. Coalesced dirty KV flush<=once/15s in existing idle cohort task, no new scheduler/network. Rare new-trigger KV flush makes restart dedup/continuity durable. Unflushed later results on abrupt process loss may be censored rather than backfilled. Detail eviction explicit. Capture categoryCONSENSUS (internal reuse only; not safety hazard). Outcome aggregate counts/means are descriptive; no Alpha promotion or safety threshold.

## Validation
7 targeted testsPASS across consensus outcome/Store registration-dedup/safety-veto regressions. Covers floor-before-recovery, wrong pool, stale/repeated clocks, exact horizon, restart state restoration, expiry/capacity, one evidence capture/no funded arm. git diff --checkPASS. No full-suite claim.

## Initial natural denominator
Cutoff19:51:23Z: existing evidence2 independent BSC tokens/decision episodes at11:14:05 and12:18:06; both preactivation and intentionally not captured. New post-load evidence0; outcome KV not yet written because there is no trigger. Thus prospective captured0, observed15/60/240=0, matureUNKNOWN0, floor-hazard0, tail outcomes0; NOT evidence of safety/profitability. Existing two examples are not merged into the forward denominator.

Health running/Paper-only, funding/registration digest unchanged0a9ed6e938ef2f7201af23b7fa201ab9104982553d68b5baaf8ddc21ff1fd24a. Early30s guard: heldfetchp952.720 vs pre2.715s, heldapply.0399 vs.0822s, passive drops0,DexPoolTimeout/connect0. Passive waitp957.57s/startup29batches and pattern1sample are immature; do not claim comparable/sustained performance. No tuning/forced cases. Evidence data/research/admission88/{pre_consensus106,post_consensus106}.json and data/research/consensus106/initial.json.
