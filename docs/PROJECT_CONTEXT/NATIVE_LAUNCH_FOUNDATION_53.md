# Native launch foundation53 RESULT

REPLY_TO: C2C-20260909-NATIVE-LAUNCH-DATA-P0-53

Independent baseline21:12:01Z: zero evm_native_launch/official_native_listing evidence; BSC native source reports limit exceeded, RH eth_getLogs failed. Official BNB documentation disables eth_getLogs on listed mainnet public endpoints. Robinhood documentation describes public RPC as rate limited and not production-grade/latency-sensitive.

Four.meme public POST token/search independently returns HTTP200 code0 and current rows; NEW and PROGRESS both verified. Use existing HttpClient, one page max30, rotate NEW/NEW/PROGRESS, receipt-time observation, raw provider createDate kept separate. INIT rows are not launched evidence; accept networkCode0 and PUBLISH/TRADE only. No list price becomes USD market price. Evidence kind official_native_listing is deliberately NOT an EVM log. Persistent source-key dedupe prevents rehydrating identical status/progress receipts. New identities enter existing discovery/hydration queue. No login, CLI, private key, watch expansion or strategy change. Failed requests retain existing5-minute low-priority backoff; held/SELL skip gates remain.

Pre-deploy held_fetch p50 .6895s/p95 2.3278s; apply p95 .04659s; passive drops0. Targeted Four/parser+runtime4 tests passed. Pons implementation and natural acceptance are recorded below.

Sources:
- https://docs.bnbchain.org/bnb-smart-chain/developers/json_rpc/json-rpc-endpoint/
- https://docs.robinhood.com/chain/connecting/
- https://github.com/four-meme-community/four-meme-ai/blob/main/skills/four-meme-integration/scripts/token-list.ts
- https://docs.ponsfamily.com/v2

Evidence: data/research/native_launch53/baseline.json, four_probe.json, four_progress_probe.json, perf_before.json.


## Implemented Pons path and limits

751a577 deployed through existing launcher (supervisor10444). Four/V2/Four/V1 rotation retains30s scheduler: Four nominal60s (NEW,NEW,PROGRESS => progress180s), eachPons120s, subject to held gates/timeouts/backoff. SingleFour page30; Pons singleBlockscout page50. Current V2 factory0x7ed598bcef8bd9edd8c97a195c6d13f40801ec7e. Official TokenLaunched decodes token/curve/deployer/pairToken/config/threshold; PoolGraduated decodes token/positionId/tokenAmount/pairTokenAmount. Neither emits a20-byte V4 AMM pool address; pool remainsNULL. Factory list only creates observer evidence/launch identity; no entry gate reads these evidence kinds directly.

Pons Blockscout endpoint https://robinhoodchain.blockscout.com/api/v2/addresses/0x7ed598bcef8bd9edd8c97a195c6d13f40801ec7e/logs?items_count=50 works without paid key. First page seeds frontier (no historical replay). Only actual indexed head advances indexed cursor; unrelated events ignored. Indexed finality=false/confirmation_depth unknown; raw source block timestamp separate from receipt. Page overflow reportedTRUNCATED, not complete chain coverage. Existing bounded100-block RPC fallback only on indexedfailure, separatecursor; it cannot advance indexedcursor. This still permits coverage loss during long downtime/pageoverflow; no unlimited catch-up or newsourcecredentials.

18 targeted tests passed:7 new/runtime/REST/V2 plus11 existingV1/Fourlog tests. Scoped diff check passed. Four REST/progress live probes succeed. Natural acceptance follows.


## Natural acceptance / final disposition

Cutoff21:21:33.535072Z, runtime loaded751a577 around21:17:50Z. Official Four listing evidence111 unique tokens,108 first-local discoveries; Pons V2 five natural TokenLaunched/PoolGraduated-kind evidence rows across5 tokens, all5 first-local discoveries. PonsV1 preserved, no new item in this short window. All current per-observer source errors empty. Old native-launch:bsc aggregate error is historical from retired RPC path, not a current FourREST failure.

Of116 distinct newly observed identities,5 had an observed price>0/liquidity>=1000 causal snapshot after receipt by cutoff; all5 BSC. Receipt-to-first-valid delays0.10,121.24,121.24,180.72,180.73s. Provider createDate-to-first-valid delays84.54–221.55s; createDate is provider-reported launch metadata, not independently authenticated creation-block time. Remaining111 are censored/unavailable at cutoff (including all5 Pons), not failed/dead. Recent20,000-snapshot read starts20:21:49Z, before this entire observation cohort, so bounded window covers the post-receipt period. No chart-price or missing-liquidity frame promoted to valid. This proves restored discovery/evidence, NOT solved universal early market coverage or tradability.

Final21:22:04Z held_fetch p50 .6916s/p95 1.4702s, apply p95 .04107s, passive drops0. Baselinep95 2.3278s; workloads/windows differ so do not call it a measured speedup. One intermediate health read returnedstale; next21:21:47 and final21:22 checks running with fresh heartbeat, no extra restart. No sustained regression observed; long-run acceptance remains unproven. Existing43 recovery retained. Final Live/Paper flags Paper-only, Live locked. Registration/activation/policy/funding/capital SHA256 match predeploy baseline.

Evidence data/research/native_launch53/acceptance.json, perf_final.json, live_final.json. Code751a577; deployment only through existing launcher, no account creation/reset, no historical observation edits, no source-derived BUY authority. Current watch capacities unchanged. Long-run provider/index coverage, page overflow and discovery-to-valid-market latency remain limits; no request-budget escalation in this tranche.
