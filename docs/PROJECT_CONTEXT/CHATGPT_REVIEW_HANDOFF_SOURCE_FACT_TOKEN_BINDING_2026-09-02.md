# ChatGPT independent review handoff — source facts vs Token binding

## Review purpose

Review a proposed separation of the current Token Context investigation into:

1. an immutable, source/evidence-version-level fact investigation; and
2. a Token-specific binding assessment that remains independent for every chain/address.

This is a design review only. Do not enable Live trading, relax evidence or safety gates, rewrite history, backfill cohorts, or treat a reused source fact as a reused Token conclusion.

## System objective

Increase the strict-forward, net-of-fee/slippage, risk-adjusted probability of profitable Paper trading in newly launched Meme Tokens. Solana is the primary chain and BSC is the auxiliary chain. Information may lead price, but a celebrity/KOL post, project metadata link, identity match, repost, promotion, or shared narrative is not automatically an endorsement, exact Token binding, or trade signal.

## Current empirical evidence

- The latest 120 Token Context assessments included 99 trigger URLs but only 47 distinct URLs.
- Calls after the first occurrence of a URL consumed about 6.126M tokens.
- A later natural forward window contained 12 assessments from `09:00Z` through `09:33Z`; all returned `no_context`.
- One exact Solana post, `https://x.com/solana/status/2095077638977310961`, was investigated for six different Tokens. Those six calls consumed 404,124 tokens and all returned `no_context`.
- After the Solana+BSC-only restart, that same exact Solana post was investigated four more times for four more Tokens, consuming another 282,846 tokens; all four again returned `no_context`. Across the observed window the one post has now received ten Token-specific full investigations consuming about 686,970 tokens, all `no_context`. A distinct exact Sam Altman post consumed 119,690 tokens and ended `insufficient_reachable_sources`.
- Source-fair ordering is deployed. It prioritizes unseen distinct source keys when alternatives exist, but deliberately does not skip same-source Tokens when no alternative source exists. It therefore cannot remove repeated full investigation of one post across multiple Tokens.
- The active chain scope is now Solana+BSC. The expanding post-deployment forward window produced at least 76 Solana and 27 BSC Tokens, 9 `WAIT` decisions and no main Paper fill. Six completed Context assessments produced four same-post `no_context`, one distinct-post `insufficient_reachable_sources`, and one metadata-triggered `no_context`.
- Main Paper currently has 4 BUY and 4 SELL trades, no open position, and realized PNL around `-$4.32` from a `$1,000` starting account. Separate onchain exploration Shadow results are not main strategy evidence.

## Current implementation

Read the current workspace through `@笔记本mcp20260902`, especially:

- `src/memetrader/autonomous_search.py`
  - `token_context_source_key`
  - `_record_token_context_assessment`
  - `search_token_context`
- `src/memetrader/runtime.py`
  - `_recent_token_context_source_keys`
  - `_source_fair_context_order`
  - `poll_dexscreener_discovery_once`
- `src/memetrader/store.py`
  - `token_context_assessments`
  - `token_context_admission_attempts`
  - `token_universe_funnel_transitions`
- related tests in `tests/test_autonomous_search.py` and `tests/test_runtime.py`.

The current `search_token_context` prompt mixes:

- source/post/event facts, independent corroboration, community amplification and public-figure actions;
- Token name, symbol, description, metadata seeds, chain/address and market snapshot;
- exact address binding and decision-evidence eligibility.

The combined result is stored in `token_context_assessments`, keyed operationally to one `token_id`. Consequently, another Token pointing to the same post repeats the full web investigation.

## Non-negotiable causal and safety boundaries

- Append-only, point-in-time records; no historical backfill or mutable cache that changes past assessments.
- Every reused fact must have a durable `available_at/recorded_at`; a Token assessment may only consume a fact available no later than that assessment/decision.
- Evidence grades remain separate: provider metadata, exact local browser body and any later revision/fingerprint cannot collapse into one record.
- A new exact body, changed content fingerprint, stronger evidence grade, correction/retraction, or expired freshness window must be able to create a new source-fact version.
- Negative source findings cannot become permanent truth. The design needs a bounded refresh rule without re-running once per Token.
- Source/post facts may be shared. Token name/CA/project-claim binding, exact-address evidence, safety, liquidity, quote, position sizing and trade eligibility may not be copied from another Token.
- A project-supplied social link remains identity/project-claim context unless independent evidence establishes a stronger relationship.
- No change may create a Decision or Paper fill merely because a source fact was reused.
- Paper and Shadow results stay separate. Live stays locked.

## Candidate architecture to review, not assume

An append-only `source_fact_investigations` lineage keyed by canonical source URL plus evidence grade and exact-body fingerprint. The first eligible Token (or event) may run a source-level web investigation. Later Tokens can consume that immutable source fact while it is fresh, then perform a separate Token-binding assessment.

Possible Token-binding tiers:

1. deterministic exact CA/address in independent, fresh evidence;
2. deterministic project-metadata link only, retained as identity/unverified project claim;
3. a bounded, lower-cost Token-specific Agent assessment using the frozen source fact plus this Token's metadata;
4. abstain when the evidence cannot distinguish same-narrative clones.

Do not assume that two Agent calls for the first Token are economical. Compare one combined first call plus reusable structured source output, a dedicated source call followed by binding calls, and other minimal alternatives.

## Independent reviewer questions

1. Is the separation causally valid and likely to improve useful source coverage without hiding false negatives?
2. What is the smallest append-only schema and lineage needed to prevent leakage and preserve auditability?
3. Which fields are truly source-level, which are Token-specific, and which must never be reused?
4. How should negative findings, refresh timing, evidence upgrades and corrections be handled?
5. Should the first Token still use one combined call, or should source investigation and binding be separate calls? Compare expected Agent cost for fanout `N=1`, `N=2..4`, and `N>=5`.
6. Can a deterministic Token-binding pass safely avoid an Agent call? Under exactly what evidence conditions?
7. What failure modes could reduce recall of early information-first opportunities?
8. What forward metrics and stop gates would prove the change improves coverage and Decision/Paper yield rather than only reducing tokens?
9. Recommend `GO`, `REVISE`, or `NO-GO`, with the smallest safe implementation path and targeted tests.

## Required review output

- Verdict: `GO | REVISE | NO-GO`.
- Incorrect assumptions or missing denominators.
- Minimal schema/lineage.
- Exact reuse and refresh rules.
- Minimal code path and tests.
- Forward evaluation metrics and stop gates.
- Explicit confirmation that no Token conclusion, Decision, safety result or trade eligibility is copied across Token IDs.
