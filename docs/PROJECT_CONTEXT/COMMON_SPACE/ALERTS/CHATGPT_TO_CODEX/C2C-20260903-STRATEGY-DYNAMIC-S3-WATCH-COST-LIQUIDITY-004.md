# C2C-20260903-STRATEGY-DYNAMIC-S3-WATCH-COST-LIQUIDITY-004

PRIORITY: P0 / USER-EXPLICIT STRATEGY CORRECTION
TYPE: DESIGN_CORRECTION / IMPLEMENTATION_DIRECTIVE
OWNER: Codex
FACT_CUTOFF_UTC: 2026-09-03T08:34:00Z
BLOCKS_LIVE: true
BLOCKS_CURRENT_HEALTHY_RUNTIME: false

## Latest user requirements

1. Every strategy family must support dynamic exits; fixed horizons are comparison baselines, not the full strategy.
2. UI must present dynamic exit policy arms under each strategy.
3. When chain-specific slippage/fees can be observed from current amount-specific routes, use observed values; frozen 4% + $0.40 remains only a modeled stress/fallback arm.
4. Liquidity withdrawal / pool collapse must be learned as a forward risk process. A token that later loses liquidity may still have had an early executable profitable exit; never remove it retrospectively from the denominator.
5. Lead ChatGPT has an active duty to discover system problems, especially strategy, news/source coverage, execution and efficiency problems. Do not rely only on Codex to raise issues.
6. Avoid unnecessary defensive/audit/re-review loops. Use current data and the smallest validation that changes an observed bottleneck.
7. Strategy 1 trading is abnormally sparse and must be causally diagnosed/fixed rather than dismissed as conservative behavior.
8. Strategy 3 should be redesigned from the current product-facing “buy first, investigate later” into `Token-first WATCH -> bounded pre-entry information confirmation -> BUY/WAIT`; post-entry information continues after BUY for position management. Preserve the old exact-paired post-entry-only lane as a causal research control, not as the permanent Strategy 3 product definition.

## Current local facts from Lead read-only inspection

### Strategy 1 sparse conversion

Recent 24h SQLite snapshot:
- Decisions: 791 WAIT, 14 REJECT, 1 CANDIDATE.
- Unique decision events: 195 WAIT events, 10 REJECT events, 1 CANDIDATE event.
- Several events were reevaluated 20-49 times with no candidate conversion.
- WAIT rejection reasons: candidate_score_too_low 332, stale/non-feature evidence large, canonical ambiguity 87, but safety rejects are only a small tail.
- 272 WAIT rows with no rejected reason are actually `no_matching_token`.
- `token_universe_funnel_transitions` shows 14,357 `candidate_evaluation/filtered/match_score_below_minimum` rows across roughly 195 events and 5,361 tokens.
- Of those filtered rows the 24h match-score median is about 15.9, p90 about 35.5, p95 about 44.8, max <52; 7,365 came from `recent_token_overlap` and 7,007 from `alias_search`.
- Current candidate threshold is `min_match_score=52`, `min_candidate_score=67`, `min_canonical_margin=5`.

Interpretation: do NOT simply lower gates. The dominant S1 problem is retrieval/binding efficiency and repeated low-information re-evaluation. Current CandidateEvaluator has exact CA / Agent exact binding / bounded alias search / recent token lexical overlap, but it does not use the already persisted exact source-link-to-token identity set as a bounded retrieval lane before broad lexical candidates. Exact source-link metadata remains identity-only, never independent decision evidence; however it can safely narrow the candidate set available for subsequent independent-evidence scoring.

### Strategy 1 execution truth

Current main S1 normal Paper path still uses DexScreener mark + configured adverse slippage for fills. Amount-specific Jupiter entry-preflight exists only as a research challenger on a narrow route-backed path. Therefore S1 should not be called amount-specific executable until final policy-size router semantics are promoted.

### Strategy 2 / Strategy 3 current implementation

- S2 already has fixed-horizon and dynamic-exit policy arms in backend/UI.
- S3 current store version `onchain-paper-narrative-runner/v3-fixed-baseline-20usdc-flat040` has already corrected the previous confound: `source_baseline_exit = ONCHAIN_PAPER_EXPLORATION_VERSION`, so treatment-disabled S3 mirrors S2 fixed baseline.
- Current product-facing S3 still clones S2 BUY then waits 60s/post-entry snapshot for information. Latest user instruction supersedes that as the desired main S3 product model.
- Preserve existing S3 v3/v4 exact-paired post-entry lane as research evidence; do not mutate or delete it.

### Chain execution/cost capability already present

- Solana Jupiter quote parser already records amount-specific minimum output, price impact bps, route-plan fee amounts, and fields for signature/prioritization/rent lamports when provider returns them.
- Current main Solana cost model still uses a frozen fallback because native-fee USD conversion / end-to-end execution evidence is not fully wired.
- BSC/Base/Robinhood `EvmZeroXPriceClient` already exists and records amount-specific 0x v2 `/price` output: minBuyAmount, gas, gasPrice, totalNetworkFee, buy/sell tax metadata, allowance requirement, simulationIncomplete and route fills. It is correctly marked non-firm/research-only; current production aggregator attempts are still empty at this cutoff.
- 0x official docs currently support BSC 56 and Robinhood 4663; firm `/swap/allowance-holder/quote` includes transaction payload, totalNetworkFee and token tax metadata. Upgrade from `price` observer to firm-quote research before EVM Paper.
- Robinhood official `/rhj/assets` supplies exact chain-4663 Stock Token contract deployments; use deterministic exact-address exclusion before Meme admission.

## Strategy model to implement

### Strategy 1 — Information + Token

Entry: information/event first plus Token identity/market confirmation.

Policy arms:
- fixed-horizon exit baseline (research comparison only);
- dynamic market exit: hard stop + trailing + staged TP + max hold + liquidity/route deterioration;
- dynamic information exit: correction/retraction, narrative decay, independent-source decay or explicit adverse new information;
- size policy remains versioned and learned forward.

### Strategy 2 — Token-only

Entry: pure Token/on-chain/market/execution.

Policy arms:
- existing fixed 15/60/240 comparison baseline;
- dynamic on-chain exit: hard stop, trailing, staged TP, max hold, activity/flow decay, liquidity/route deterioration;
- future hazard-aware size/exit based on strictly entry-available liquidity/creator/surface features.

### Strategy 3 — Token-first WATCH -> information confirmation -> entry

This becomes the product-facing family.

State machine:
`TOKEN_TRIGGER -> WATCHING -> INFO_PENDING -> CONFIRMED_BUY | REJECTED | EXPIRED -> (if bought) POST_ENTRY_MONITORING -> EXIT`

Entry must be bounded in latency; do not wait indefinitely for a rich narrative report. First version should freeze a small decision window (suggest 30-120s range configurable, choose one frozen value based on current Token Context scheduling capacity) and use only information observed/ingested before the S3 decision.

Pre-entry confirmation may use:
- exact local social/news content already captured;
- independent source evidence available during the watch window;
- public-figure/creator/project linkage as correctly role-classified context;
- negative signals such as correction/denial/promotion-only/no independent support;
- Token on-chain state rechecked at decision time;
- amount-specific executable quote at final size.

Do not copy S2 BUY into this new arm. The old exact-clone lane remains as `S3 post-entry causal control` so the incremental value of post-entry information can continue to be studied separately.

To avoid losing the earliest moves while waiting for context, preserve one future candidate arm (do not activate immediately): `small probe entry -> confirm -> add/exit`. First implement full confirm-before-entry as a clean estimand; later compare probe-first only if latency data show confirmation cost is economically large.

## Shared dynamic-exit architecture

Create/reuse a single policy interface, with strategy-specific feature adapters, rather than three separate exit engines.

Common deterministic components:
- hard stop;
- trailing stop;
- staged take profit and **cost-aware sell fractions**;
- max hold;
- executable sell quote / no-route state;
- liquidity absolute floor;
- liquidity velocity/drop;
- amount-specific sell-capacity deterioration;
- transaction/buy-sell-flow deterioration when available.

Strategy-specific additions:
- S1: narrative/event decay, correction/retraction/new adverse evidence.
- S2: on-chain only; no narrative features.
- S3: post-entry information state plus all deterministic execution/risk exits.

Fixed-horizon exits remain baseline arms for causal/economic comparison. UI must never present `fixed horizon` as the strategy itself.

### Cost-aware partial exits are required

Current fair notional is only $20 and the frozen fallback charges $0.40 per economic SELL. A 20% first take-profit tranche can therefore be only about $4 before price appreciation, making a $0.40 fixed fee alone roughly 10% of that tranche before slippage/tax. Blindly executing every staged TP can destroy the very edge being tested.

Before each non-emergency partial exit, request/derive the amount-specific SELL economics for the proposed remaining/fractional raw amount and freeze:
- gross/minimum recovery;
- all currently observed route/network/tax costs;
- fee-to-gross ratio;
- net cash recovery;
- alternative larger/full-exit quote when bounded request budget permits.

A policy arm may coalesce/skip a tiny TP tranche or sell a larger fraction when the partial fill is economically dominated by its transaction cost. Hard safety/liquidity emergency exits are not blocked merely because fees are high; route availability still governs execution. Do not invent one universal ratio threshold from hindsight—register a small set of forward candidate rules and compare them.

## Liquidity withdrawal / early-profit research

Do not define later collapse as an entry exclusion label. Build a forward estimand around two competing events:

1. `first_executable_profitable_exit_at` for the actual policy-size position after all observed costs;
2. `liquidity_death_at` / `sell_route_death_at`.

Derived forward outcomes:
- profitable-before-collapse yes/no;
- earliest and latest executable profitable exit time;
- max executable net return before collapse (using only quotes actually sampled at their times, never future interpolation/ATH);
- time from first warning to route death;
- whether the dynamic policy would have exited before death.

First warning features should be available at the time:
- same-pair liquidity drop rate;
- amount-specific sell minimum-output deterioration;
- route count / route capacity deterioration;
- pool reserve/vault or remove-liquidity event where protocol-specific evidence is available;
- creator/LP ownership or unlock/withdraw authority only when actually verified.

Do not call an unclassified Dex liquidity drop “developer rug” without on-chain attribution.

Initial policy challenger should use simple preregistered thresholds/2-of-N warnings, not a complex ML hazard model. The existing liquidity-survival v3 ledger provides descriptive input; promotion requires forward policy comparison.

## Dynamic execution costs

Cost truth tier, per fill:

1. `OBSERVED_EXECUTION` — actual simulated/built/firm amount-specific route and provider/network cost fields sufficient for the fill semantics.
2. `QUOTE_OBSERVED` — amount-specific minimum output / firm price, price impact, route fee/tax/network-fee estimate observed, but no transaction execution.
3. `MODELED_FALLBACK` — frozen 4% + $0.40 or chain-specific fallback when provider fields are unavailable.

Never combine tiers silently.

Solana:
- prefer amount-specific Jupiter route output / RTSE-capable order/build semantics when available;
- use observed price impact/min-output and returned signature/prioritization/rent fee fields with contemporaneous SOL/USD conversion if possible;
- retain 4%/$0.40 as stress/fallback arm, not “real Solana fee”.

BSC/Robinhood:
- implement 0x v2 firm-quote research from `/swap/allowance-holder/quote` when API key/public taker prerequisites are available;
- capture min buy, transaction gas/gasPrice, `totalNetworkFee`, token buy/sell taxes, allowance requirement, simulationIncomplete, route fills;
- optionally fixed-block Anvil/eth_call transaction simulation for sellability/revert confirmation;
- only promote to Paper when round-trip BUY->actual acquired/minimum raw->SELL and cost completeness are demonstrated.

## Strategy 1 P0 fix — do not lower thresholds first

Implement an `exact source-link identity retrieval` lane before broad alias/recent-overlap filtering:

- From the current event's eligible exact public-item URLs, look up only Token source-link/exposure rows that were already recorded by the decision time.
- Freeze the complete matching Token identity set available as-of the decision.
- Use this only for candidate retrieval / ambiguity-set construction (`role=identity`, no score/feature boost by itself).
- Each candidate still needs independent event evidence, canonical logic, safety and executable route before BUY.
- Same source URL linking to many Token clones should produce explicit `identity_set_fanout`, not an arbitrary winner.
- Bound candidate count and dedupe by chain/address.

Also stop repeated low-information evaluations from dominating work:
- if event evidence revision + as-of identity set + candidate-set fingerprint have not changed, reuse prior WAIT terminal until a meaningful new source/candidate/snapshot trigger arrives or a bounded retry checkpoint is due;
- preserve immutable decision history, but do not burn broad search every 25/60/150/300s merely to reproduce the same no-match set.

Acceptance metric after deploy: forward reduction in repeated candidate-filter work per unique event and improved `event -> nonempty bounded identity set -> ranked candidate` conversion, without increasing false canonical / safety rejects by simply lowering gates.

## UI changes

Exactly three top-level strategy tabs:
1. S1 Information + Token
2. S2 Token-only
3. S3 Token -> Information Confirmation

Within EACH strategy show:
- active entry/sizing/exit/cost policy versions;
- `Fixed baseline` and `Dynamic exit` as internal policy arms;
- active/research/promotion state;
- chain filter `ALL / SOL / BSC / ROBINHOOD` (Base retained in research detail);
- `OBSERVED_EXECUTION / QUOTE_OBSERVED / MODELED_FALLBACK` badge and fee breakdown;
- dynamic exit reason and last risk trigger;
- liquidity-risk state / route state.

S3 additionally shows timeline:
`Token trigger -> watch start -> information evidence -> confirmation decision -> executable quote -> BUY/WAIT -> post-entry evidence -> exit`.

Move the old exact-clone/post-entry-only S3 to a collapsed Research Lab card labelled causal control; it should no longer define the main Strategy 3 tab.

Research Lab remains collapsed by default.

## Lead proactive-discovery obligation

Persist this as an operating rule, but keep it lightweight. At material cycle boundaries or when a natural result changes interpretation, Lead ChatGPT should proactively inspect a bounded dashboard of:
- S1 funnel conversion / repeated WAIT / exact binding latency;
- news/KOL source freshness and coverage gaps;
- Token Context duplicate/reuse/Agent efficiency;
- per-chain route/no-route/cost completeness;
- liquidity death and early profitable-exit windows;
- strategy/policy-arm forward PNL/drawdown/tail/no-route;
- UI claims vs backend truth.

If Lead finds a material problem, create one delta handoff and notify Codex. Do not run recurring generic audits, duplicate reviewers or full-suite tests merely for reassurance.

## Ordered implementation tranches

P0-A — S1 conversion efficiency
1. Add as-of exact source-link identity-set retrieval to CandidateEvaluator/Store without making identity decision evidence.
2. Add stable candidate-set/evidence fingerprint so unchanged WAIT/no-match evaluations do not repeatedly execute broad discovery.
3. Keep current thresholds initially; measure natural forward conversion after the retrieval fix.

P0-B — S3 new top-level pre-entry confirmation family
1. Add append-only `token_information_watch` registration/cohort/decision lineage or minimal equivalent using existing ledgers.
2. Token-only trigger creates WATCH, not BUY.
3. Bounded pre-entry context collection uses only as-of data; final Token/safety/route recheck before CANDIDATE/BUY.
4. Old S3 exact-paired post-entry lane remains research-only.

P0-C — shared dynamic exit contract
1. Make fixed/dynamic policy arms machine-readable for S1/S2/S3.
2. Reuse current PaperPolicy/S2 dynamic components, avoid a framework rewrite.
3. Add liquidity deterioration warning inputs and strategy-specific narrative adapter.

P0-D — dynamic observed execution-cost adapters
1. Solana: promote observed quote/fee fields into cost breakdown with explicit truth tier; keep fallback.
2. EVM: implement 0x firm-quote research client for BSC/Robinhood from existing price client; no signing/submission.
3. Only after natural forward round-trip samples decide Paper promotion.

P0-E — liquidity-collapse early-exit challenger
1. Extend current liquidity-survival outcomes with strict-forward executable-profitable-window joins/targets; no future interpolation.
2. Register simple dynamic liquidity-warning exit challenger.
3. Compare early exit net result vs collapse/write-off.

P0-F — UI IA update
Implement after backend fields for P0-B/C/D exist; do not fake unavailable fields.

## External research basis

- Hummingbot PositionExecutor uses a reusable triple-barrier model (stop loss, take profit, time limit, trailing stop); borrow the pattern, not the framework.
- Jupiter 2026 Metis/Ultra docs describe real-time slippage estimation and route/execution optimization; current local quote client already captures provider fields that can improve truth-tier reporting.
- 0x v2 official docs currently support BSC 56 and Robinhood 4663 and expose firm quote transaction, totalNetworkFee and token tax metadata.
- Robinhood Chain official docs identify chain 4663/ETH gas and `/rhj/assets` exact Stock Token deployments.
- Foundry Anvil supports fixed-block EVM forks for bounded transaction/sellability simulation.

## Release/causal guard

- Live locked.
- No historical winner backfill.
- Old policy/strategy versions immutable.
- Do not lower S1 thresholds merely to increase trade count.
- Do not retrospectively exclude rug/liquidity-death tokens.
- No Agent concurrency increase for S3 watch; scheduling must be bounded/fair.
- Do not call quote-only/model PNL executable.
- Do not add redundant audit/reviewer loops.

## Immediate Codex action

Start with P0-A. After the smallest coherent S1 identity-retrieval + unchanged-WAIT suppression implementation and targeted tests, send a checkpoint to Lead ChatGPT with forward activation/version, then proceed to P0-B while Lead continues reviewing natural S1 evidence.
