# EVM LP custody109 — implemented; runtime acceptance incomplete

REPLY_TO: C2C-20260909-EVM-LP-CUSTODY-109

## Current disposition
Code c865f16 was loaded around 2026-09-09T20:14Z. Final audit-only correction 5c5424a is committed/pushed but NOT loaded: the scoped supervisor/Paper restart tool call was rejected with "blocked by policy". No bypass was attempted. That rejected call did not execute its report-writing step either.
At 20:18:39.922416Z health=running, funding version remains chain-meme-trader/funding-20260906-v002-final-1000. LP Shadow KV absent: no natural captured denominator or horizon outcome demonstrated.
Held fetch p95=4.2653s vs pre-stage2.5042s exceeds the guard; apply=.07074s vs .08258s, pattern=8.4773s vs9.6302s. This is a short non-controlled window, not proof of causal regression. Runtime acceptance is INCOMPLETE/GUARD_EXCEEDED, not PASS. Deployment/reversion is blocked on the denied process-control surface; do not bypass. Read-only evidence: data/research/admission88/post_lp109_readonly.json; pre_lp109.json.

## Exact behavior
Consume existing full goplus_evm only: no new provider request, timer, account or BUY permission. The nested assessment cannot change existing allow/status/hard rejects/soft-hazard decision. Separate bounded LP_SHADOW 15/60/240-minute outcomes use naturally recorded exact-pool snapshots, causal clocks and existing floor/censoring rules; no history seeded.

Only a single reported exact pool with liquidity_type=UniV2 is supported. Require chain/token/pool binding; ambiguous multi-pool, V3/V4/CLMM, curve and unknown venue remain UNKNOWN. Binding is provider evidence, not onchain attestation. Validate finite percentages, balances versus supply, unique holders, count/list coverage, and sums. Missing fields UNKNOWN; contradictory complete coverage LP_COVERAGE_INCONSISTENT, never safe.
Burn recognizes exact zero/dead addresses; tag alone does not prove custody. Locks require amount and available/unexpired lock clocks. Tagged/contracts with uncertain custody remain unknown. Report listed/locked/burned/unknown fractions and top unlocked non-custody concentration. Descriptive bins: majority >50% LP_UNLOCKED_CONCENTRATED; locked/burned >=90% LP_LOCKED_OR_BURNED_HIGH. Neither is a veto or safety guarantee; no fitted return threshold.
Final 5c5424a explicitly keeps LP_SHADOW hard_veto=[] instead of the outcome tracker default copying descriptive reasons. This is an audit label correction, not a trading authority change. Initial running version can still mislabel that field, so do not interpret LP reasons as executed vetoes.

## Validation and boundaries
54 targeted safety/LP/outcome tests passed after correcting incomplete test pending metadata handling; final LP/outcome set13 passed. git diff --check passed. No full-suite claim.
Pre-stage immutable funding/registration hash: 0a9ed6e938ef2f7201af23b7fa201ab9104982553d68b5baaf8ddc21ff1fd24a. No accounting/registration/history writes were added. Post-stage immutable hash and natural coverage acceptance remain to verify; no profit or rug-prevention claim.
Changed modules: evm_lp_custody.py, preentry_safety.py, safety_veto_shadow.py, store.py, runtime.py; tests/test_evm_lp_custody.py.

Official semantics: https://docs.gopluslabs.io/reference/response-details and https://github.com/GoPlusLabs/OpenAPI/blob/main/SecurityAPI.md . Top-level LP holders are not assumed to bind an arbitrary member of a multiple-pool dex list. Current requery data is never historical evidence.

Next safe boundary: resolve supported process-control availability, then load final audit correction or revert only109 if comparable latency remains unacceptable. Preserve107/108, funding/history and Live lock. No expansion or promotion before prospective evidence.
