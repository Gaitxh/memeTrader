# Multi-agent narrative103 — design ready, quality gate pending

REPLY_TO: C2C-20260909-MULTIAGENT-NARRATIVE-103
Disposition: DEFERRED_PENDING_CONTEXT_TRIM_NATURAL_QUALITY. No new worker/Scout/strategy/overlay deployed. This is distinct from failed-impulse cooling103.

## Current evidence

The trim e271373 was deployed18:43:03Z on2026-09-09, adding only ephemeral AutonomousSearch project_doc_max_bytes=0. Bounded current-version narrative result lookup returns two completed calls, both BEFORE deployment:

| Result ID / completed UTC | Model / reasoning | Input | Cached input | Output | Total | Sources / state |
|---|---|---:|---:|---:|---:|---|
|234587 /12:01:16Z|gpt-5.6-luna /low|86957|56320|830|87787|0 /UNKNOWN|
|238092 /13:09:02Z|gpt-5.6-luna /low|122755|92160|1982|124737|0 /UNKNOWN|

Both record returncode0 and valid_structured_output; valid JSON does NOT validate source quality or exact binding. Neither ran a verifier. No completed post-trim narrative invocation is available. Other existing token-context assessment latest1338 is Sep3, verifier latest3 is Sep3: neither supplies post-trim acceptance.

Current narrative KV daySep9: calls2, actual_tokens212524, reserved_tokens120000. The existing admission reserves60000 per checkpoint against240000/day: max(actual,reserved)+60000=272524, so a further checkpoint cannot enter under today's budget. Preserve the cap, reservation and natural next-day reset semantics; do not manually clear quota, force a call, force a trade or create a new Codex session. The remaining tracked quiet_renewal cohort94663 has all3 checkpoints FAMILY_PRIORITY_SKIP; do not relax family selection solely for this experiment.

Evidence: data/research/narrative103/state_readback.json, results_readback.json, other_agent_frontiers.json. Read-only KV, version/kind-indexed bounded evidence results, and latest-ID agent records; no production broad scan. Existing code confirms shared runner, no-source skips verifier, core-idle gate, latency guard, actual-principal/healthy-pool/safety extension conditions. No new code tests are required for this design-only boundary; earlier101 argument tests do not substitute for natural quality acceptance.

## Minimal design after the prerequisite passes

Reuse NarrativeHoldV2 checkpoints/cases, existing AutonomousSearch profiles, shared2-slot semaphore, reservations and daily actual-token cap. No third framework, new timer, paid source or separate Codex implementation session. Agents remain read-only evidence producers. Root Codex remains the sole implementation writer.

1. News/Event Scout A uses the current token_context Luna profile with a focused role prompt: real external event, novelty, independent origins, publication/availability clocks, corrections. It may find news without a CA; that is not endorsement or a token selection instruction.
2. Social/KOL Scout B uses the same existing profile with a distinct role prompt: exact CA/cashtag association, independent newly propagating origins since the previous checkpoint, project ownership, copied stories, trading calls/promotion/impersonation and high-fanout ambiguity. Existing local X hints remain untrusted. No usable news/lead supply means do not blindly run both scouts. Start sequentially by default; overlapping A/B is optional only with already-usable public leads, free shared capacity and passing core-idle/latency guard. Never exceed2 active workers.
3. Independent Terra verifier C runs only if A/B or previously available checkpoint evidence supplies usable public URLs. Deduplicate origin groups and token binding subjects into the existing verifier invocation. If source supply is empty, end the checkpoint UNKNOWN with no verifier or further retry/scout cascade. Recheck idle/quota before admission; C cannot add a third parallel slot.

One existing checkpoint reservation covers the whole A/B/C attempt; it is not60000 separately per Scout. Charge all actual attempts including fallback. If the available budget cannot cover the next worker, record BUDGET_SKIP/UNKNOWN rather than increase the budget. Retain current per-checkpoint source bound; distribute it across roles and deduplicate instead of multiplying it. Role and run IDs plus actual model/reasoning/usage remain persisted.

Public fact reuse is keyed by canonical source URL/origin/event identity with first local availability and verification version, independent from portfolio accounts. Same token+pool overlapping cohorts reuse facts and one eligible research checkpoint where causally compatible, with separate case references; later reawakening has its own episode, baseline and cutoff. Never copy a later result into an earlier cohort. A source first retrieved after the checkpoint cutoff cannot support that checkpoint's hold decision; it becomes an untrusted/fresh lead for a later cutoff, preserving96 no-backdate semantics. Published earlier is necessary but does not imply locally available earlier.

## Deterministic states and trading boundary

- UNKNOWN: no adequate causal sources, unsupported model, missing binding, budget/quality gap.
- PROJECT_ONLY: only verified project-owned channels; not independent diffusion.
- PROMOTION: trading-call/promo/copy amplification without independent event support.
- REAL_EVENT_EMERGING: verified novel event but incomplete exact-token association or no verified new-origin growth; no hold extension.
- CONFIRMED_EXPANDING: verified real novel event, frozen exact binding, distinct independent origins and genuinely new verified origins since prior eligible checkpoint; current safety/freshness conditions still required.
- CONTRADICTED: verifier-established retraction, impersonation, false association or material contradiction; no extension.

These proposed labels are not yet runtime output/API changes. Existing96 states and exit semantics remain intact. Future aggregator counts new independent origin groups, not raw mention count or reused metadata membership. No Agent can select another CA, trade, override hard stop/trailing/floor or retain a loss on narrative alone. Extension requires actual settled principal recovery with remaining runner, healthy fresh original pool and no hard/soft hazard; source confirmation alone is insufficient.

## Acceptance and stop conditions

First obtain a natural post-trim token_context/fact_verifier result at unchanged quota. Verify requested/actual model, structured output and exact role schema, usage materially below the oversized baseline for comparable prompt/search work, public URL usability, publication/local availability and token-binding semantics. A zero-source result may be an honest UNKNOWN but cannot alone demonstrate positive-source binding/verifier quality. No sample is not failure of the trim.

Only then implement focused role/dedup/aggregator tests: two-role source reuse; empty sources=>no C; same-name/high-fanout not endorsement; copied origins count once; new origins compared to prior checkpoint; future local availability excluded; distinct reawakening episode; no quota or2-slot bypass; hard/trailing/floor/safety precedence. Start observer-only if source quality/cost remains uncertain. Trading-effect promotion must retain current guard and be separately supported; never promote a weak or unverified result for the sake of running multi-agent research.

Stop/defer on CLI override failure, materially worse output quality, missing causal source evidence, budget exhaustion or held/SELL latency regression. No automatic retries or budget expansion. This request remains evidence-gated pending natural output, not implemented multi-Scout capability.
