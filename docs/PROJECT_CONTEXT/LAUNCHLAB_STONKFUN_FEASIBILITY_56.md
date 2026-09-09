# LaunchLab / StonkFun feasibility 56

## Verified sources and bounded probes

Official Raydium SDK program ID: `LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj`:
https://github.com/raydium-io/raydium-sdk-V2/blob/master/src/common/programId.ts
Official read-only public list, no credential/security requirement:
https://docs.raydium.io/api-reference/launch-mint-v1-endpoints/discovery/list-mints-with-sorting
https://launch-mint-v1.raydium.io/get/list?sort=new
Protocol overview: https://docs.raydium.io/user-flows/launchlab-overview

Raydium's own list supplies platformInfo.name=StonkFun and web=https://www.stonkfun.xyz for both platform pubKeys `4E876qZTE9FJMrBzgVtBrSrzz2TLivB5Y5QXPjB4gZL7` and `6BwHHDg3u1854jC8PDLXvR4spTcLNaoBxLJNGC4nTESt`. Thus this binding is independently supported by official Raydium API, not merely a third-party address. No on-chain ownership/finality verification claimed. The SDK default platform is not substituted for StonkFun. Per-token configId and quote mint vary: samples include NVDAx and USDC, so raw curve amounts cannot be assumed SOL/USD.

Two HTTP200 unauthenticated probes at03:57:08.758562Z and03:58:16.128177Z took1.775s/1.180s, each returned100 rows. Three new identities appeared in67.37s. Newest provider createAt was77.76s/84.13s old at receipt. This is a bounded indexed feed, not full-chain/subsecond delivery. Separate campaign config endpoints returned non-JSON and were not relied on; no success claimed for them.

First30 newest rows at first receipt:23 absent from local tokens at the bounded lookup; provider age77.8–890.8s. Existing7 and their first valid snapshots are in comparison.json. Absence proves additional local coverage at lookup, not precise on-chain lead time. No historical first_seen or snapshot was inserted by the probe.

## Implementation boundary

f059c05 adds LaunchLabObserver to the existing low-priority native discovery rotation. Existing30s scheduler and per-call4s timeout remain; one request per observer (3s HTTP timeout), at most100 rows. Resulting nominal rotation: LaunchLab150s, PonsV1/V2 each150s, Four average75s. Total scheduler request starts are not raised; this explicitly trades some old-source cadence for broader coverage. Upstream SDK/API fee limits are not inferred as unlimited.

Only provider createAt at/after observer activation and no later than response receipt is admitted. Older first-page rows are ignored, so restart never replays historical listings. Evidence uses receipt clocks, stable token+pool key, exact Solana casing; durable evidence dedupe precedes hydration. Raw progress/config/quote-unit fields are preserved only on admission, not polled independently. There is no executable quote, BUY authority, market-price conversion, new strategy, watch-cap expansion, or funding change. Held/critical gates and5min source-error backoff are reused. Provider finality remains false.

Nine targeted tests passed: two LaunchLab causal/identity/envelope tests plus seven native runtime/Four/Pons tests. git diff --check passed. Tests do not prove Alpha or economically usable curve liquidity.

Evidence: data/research/launchlab56/new.json,new2.json,comparison.json,immutable_before.json,before_*.json,after_*.json,rounds.json.

## Controlled deployment / natural acceptance

Loaded code f059c05 via existing Paper launcher around04:00:42Z. First LaunchLab round04:02:45.606131Z returned9 prospective identities,7 first-local. Seven new identities reached hydration around04:02:48.25Z (~3s); at the subsequent bounded read one had a qualifying market snapshot, others remained no_pair. Already-known identities are not claimed as new. Evidence in natural_rounds.json and natural_tokens.json.

Final health running/ok; same active funding version, Paper only/Live locked. All7 immutable funding/registration/activation table hashes match. Passive drops0; Dex pool timeouts0/connect errors0. held_fetch p50/p95 .802/2.220s versus baseline .730/2.697s; held_apply_exit p95 .0744s versus .0431s; pattern p95 6.828s versus6.927s. Native task p95 4.105s includes other native source timeouts, not an isolated LaunchLab request latency. Short startup window and changed live workload do not establish long-run non-regression; apply latency increase is retained as a caveat. Initial health stale then running, no false all-green startup claim.

Disposition: DEPLOYED_IDENTITY_COVERAGE_PASS_SHORT_WINDOW; tradable pre-graduation coverage NOT established. No gold-dog strategy enabled. API progress freshness/calibration and on-chain platform-owner proof are not claimed. Collector saves progress fields only on new admission. Low-rate sampling cannot cover every burst;100-row latest-page truncation remains visible. No extra source polling task or higher request-start budget.
