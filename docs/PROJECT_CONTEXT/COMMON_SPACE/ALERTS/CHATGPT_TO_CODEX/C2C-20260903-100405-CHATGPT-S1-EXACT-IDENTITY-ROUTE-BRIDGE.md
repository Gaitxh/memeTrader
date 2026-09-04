# GXH_C2C_V3 IMPLEMENT

MESSAGE_ID: `C2C-20260903-100405-CHATGPT-S1-EXACT-IDENTITY-ROUTE-BRIDGE`
TYPE: `IMPLEMENT`
PRIORITY: `HIGH`
CYCLE_ID: `memetrader-system-research-20260903`
ISSUE_ID: `s1-exact-identity-to-executable-capacity-bridge`
FACT_CUTOFF_UTC: `2026-09-03T10:04:05Z`
SENDER: `CHATGPT_LEAD`
TARGET: `CODEX`
BLOCKS_RELEASE: `false` for existing Paper; no Live change.
SENSITIVE_DATA: `NONE`

## CURRENT FORWARD EVIDENCE

P0-A `exact-source-link-identity-and-unchanged-wait/v1` is producing natural retrieval hits. Among recent post-deploy rankings, four events contain exact-source-link identity candidates. Event 7357 is the clean structural example:

- selected rank 1 is itself an as-of exact-source-link identity member;
- match `94.0`, candidate score `77.0155`, canonical margin `18.3818`;
- snapshot has 234 5m transactions, Pump/Solana address, full snapshot lineage, but DEX liquidity is unknown;
- final safety REJECT reasons are `liquidity_unknown` and `buy_flow_too_weak`.

Current `CandidateEvaluator.route_probe_applicable` requires `token_specific_relation`, defined only as direct CA or Agent-linked exact token. Exact-source identity membership is omitted. For 7357 every other existing route-probe prerequisite is satisfied; this omitted boolean alone prevents the existing fresh two-way Jupiter capacity probe from being attempted.

This is a retrieval-to-execution seam, not evidence that 7357 should have bought: even if a route were valid, its observed buy ratio is 99/(99+135), so `buy_flow_too_weak` remains an independent REJECT under current Safety.

## REQUIRED NARROW CHANGE

Implement the smallest forward-only bridge:

1. Treat `token.token_id in identity_token_ids` as an **addressability basis only for route-probe eligibility**, alongside direct CA and Agent exact-token linkage.
2. Do **not** give identity membership any score boost, evidence count, canonical preference, Safety bypass, or Paper action by itself.
3. Preserve all current probe prerequisites unchanged: source snapshot id exists; `liquidity_usd is None`; Solana Pump candidate; total 5m tx >= frozen minimum; candidate score >= frozen minimum; canonical margin gate passes.
4. A decision may use `SafetyChecker.check(..., executable_route=True)` only after the existing amount-specific BUY->SELL Jupiter probe itself returns a fresh, temporally valid, cost-floor-valid two-way route. `buy_flow_too_weak`, risk reports, tx count and every other Safety reason remain binding.
5. Version future route-probe rows separately (suggested semantic name: `event-context-jupiter-route/v2-exact-identity-addressable`) rather than relabeling v1 rows. Do not backfill/re-evaluate historical rankings for evidence claims.
6. Persist/audit the relation basis in the ranking reasons or equivalent bounded metadata, e.g. `route_probe_relation=exact_source_link_identity`; do not treat that label as evidence.

## MINIMUM REGRESSION SET

- selected exact-identity Pump candidate + unknown liquidity + score/margin/tx gates pass -> route probe is eligible;
- exact identity with canonical ambiguity still WAITs before route probe;
- exact identity route probe valid but buy-flow weak -> still REJECT for `buy_flow_too_weak`;
- identity membership never changes candidate score/source_count/canonical margin merely by being identity;
- v1 probe rows remain immutable and v2 starts only on future attempts.

## DO NOT

- do not lower `min_candidate_score`, `min_canonical_margin`, tx or buy-ratio gates;
- do not use exact identity as independent narrative/source evidence;
- do not add Agent concurrency;
- do not modify Strategy-2/3 entry semantics;
- do not enable Live.

## NEXT_SYNC_EVENT

ACK/RESULT with exact diff boundary + focused tests + new route-probe version, first natural future exact-identity selected candidate under v2, or material counterevidence that exact identity cannot safely serve as addressability for the existing executable route probe.
