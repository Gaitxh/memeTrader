# ChatGPT independent review handoff — exact source-link canonical identity

## Review purpose

Review whether a Token's provider-supplied social-post URL, when it exactly matches a fresh local Observation already accepted into the same Event, may be used only to disambiguate the canonical Token candidate set. It must not become independent confirmation, endorsement, safety evidence or trade eligibility.

## System objective

Improve the strict-forward conversion from fresh information and newly launched Solana Tokens into correctly attributed, executable Paper candidates. Avoid both missed information-first opportunities and buying an arbitrary same-name clone. BSC is auxiliary; Live remains locked.

## Current forward evidence

- Decision `2948`, Event `5189`, evaluated at `2026-09-02T13:13:27Z`, ranked two same-name Solana Tokens.
- Rank 1 `J9Gm…pump` scored `57.9568`; rank 2 `BUoY…G6DRF` scored `57.9506`. Raw canonical margin was only `0.0061`.
- Both had approximately `$2,744` market cap, unknown liquidity and zero 5-minute transactions at the decision time.
- Before the decision, rank 1 had a provider-metadata source link to exact local Observation `7120` in the Event: `https://x.com/nikitadevelops/status/2095128226393620918`. Rank 2 had no matching source link.
- The post is a project/community statement, not an independent source and not an exact CA statement. The Token was created before the post and the event contained several related X posts; identity linkage does not establish economic value.
- A strict 24-hour as-of query found five multi-candidate decisions where at least one candidate had an exact source-link match available before decision time.
- In two Event `5189` decisions, exactly one of two candidates had the matching link and the selected Token happened to be that candidate, but the current scorer did not use this fact.
- In Event `4989`, 16 candidates existed and five different Tokens all linked to the same exact Solana post. The scorer selected an unlinked candidate. All five linked Tokens were created in the same second and had nearly identical tiny market state with zero 5-minute activity. This is evidence that an exact source link can define an identity-linked set but cannot necessarily select one Token within a fanout.
- Existing `provider-post-ambiguity` and `information-first-shadow` records remain append-only and strategy-neutral. Do not reinterpret or backfill them.

## Current implementation to inspect

Use the configured workspace connector and inspect:

- `src/memetrader/strategy.py`
  - `CandidateEvaluator._match`
  - `CandidateEvaluator._quality`
  - `CandidateEvaluator.discover_and_decide`
  - ranking persistence and canonical-margin handling
- `src/memetrader/store.py`
  - `token_source_links`
  - `token_source_links(...)`
  - `event_observations(...)`
  - `information_first_shadow_*`
  - `provider_post_ambiguity_*`
- relevant tests in `tests/test_core.py`.

The current lexical scorer intentionally ignores provider/profile URLs. Exact CA evidence and independently verified Agent binding are stronger paths. This review concerns only an intermediate identity/canonical-mapping fact.

## Non-negotiable boundaries

- Strict as-of use: `first_observed_at`, Observation `observed_at/ingested_at`, and normalized URL match must all be available no later than evaluation time.
- Provider metadata remains an unverified project identity claim. It cannot increase event attention, source independence, safety, route validity, position size or trade eligibility.
- Same-post fanout must remain visible. A shared link cannot manufacture one canonical winner.
- No history rewrite or winner backfill. Any experiment needs a new activation point and append-only denominator.
- Main Paper still requires existing evidence, canonical-margin, safety, market and execution gates.
- Do not use an Agent to decide a deterministic exact URL equality. Agent use is only for genuinely semantic uncertainty.

## Questions for three independent reviewers

1. Should exact as-of source-link equality be ignored, used as a hard identity-set filter, or used as a bounded canonical-score feature?
2. When exactly one candidate links the accepted Observation, is that sufficient to resolve identity while remaining insufficient for a trade?
3. When `N>=2` candidates link the same post, should the system abstain, use onchain/execution data inside the linked set, or run a separate forward Shadow cohort?
4. How should event clustering across several related posts affect URL-level identity?
5. What is the smallest append-only experiment that measures recall, wrong-clone risk, route availability and net-of-cost outcomes without changing production Strategy?
6. What pre-registered stop gates should prevent an identity feature from increasing false positives?
7. Recommend `GO`, `REVISE`, or `NO-GO`, with a minimal implementation and targeted tests.

## Required output

- Verdict: `GO | REVISE | NO-GO`.
- Causal/temporal failure modes.
- Exact identity-set rule and fanout behavior.
- Minimal schema or existing-table reuse.
- Forward metrics, denominators and stop gates.
- Minimal code path and tests.
- Explicit confirmation that identity linkage alone cannot create a Decision, safety pass or Paper fill.
