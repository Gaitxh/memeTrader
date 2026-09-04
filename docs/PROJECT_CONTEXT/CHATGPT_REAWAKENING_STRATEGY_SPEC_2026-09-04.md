# REAWAKENING Strategy Family — Strict-Forward Specification

Date: 2026-09-04
Status: `V5 ENTRY FAMILY DESIGN / NO HISTORICAL BACKFILL`

## 1. Estimand

Test whether an existing Meme market that was demonstrably dormant under local observation becomes profitably tradable after a new, broad and executable burst.

This is not:

- a delayed launch strategy;
- a new pool/migration classifier;
- a retrospective label applied after a price spike;
- “old token with any volume increase”;
- social-news revival unless the on-chain reawakening trigger itself exists.

## 2. Episode identity

A cohort key is:

`(entry_family_version, token_mint, exact_market_surface_id, dormant_baseline_id, crossing_id)`

A token can have several future episodes only when each has a new valid dormant baseline observed after the previous episode resets/closes. A confirmed dead surface never re-enters. A new pool is a new surface/cohort and never repairs the old pool’s outcome.

## 3. Required pre-trigger observation

A reawakening decision requires a baseline that existed and was durable before the trigger.

Baseline fields:

- pool/token/surface identity;
- observation start/end;
- source coverage/gap rate;
- trade count/intensity and inter-arrival distribution;
- buy/sell quote flow;
- effective buyer/seller breadth;
- price/recovery variation;
- exact vault/liquidity path;
- full-position route/sellability observations where available;
- pool age and last prior activity;
- `available_at` and baseline-definition version.

No baseline is created from a query made after the burst and backdated to earlier chain history for the active production cohort. Historical replay may validate code separately but never enters the forward denominator.

## 4. Data-quality qualification

A quiet interval can mean a dormant market or a dead collector. Baseline qualification therefore requires:

- source/slot heartbeat advancing;
- bounded gap fraction;
- exact surface identity unchanged;
- sufficient observation duration/coverage under the registered version;
- no unresolved terminal account alert;
- explicit left-censor status for markets older than local history.

If coverage is inadequate, status is `baseline_unavailable` rather than dormant.

## 5. Dormancy components

Use robust local distributions, not one raw zero threshold:

- low trade intensity relative to the token’s observed history;
- long but genuine inter-arrival times;
- low absolute quote volume;
- low effective breadth/new-buyer flow;
- low valid-price/recovery variation;
- stable exact reserves/liquidity;
- no recent launch/migration/new-surface event.

A route may be absent during dormancy, but `route_recovered` is then a separate trigger component and executable entry still requires the current amount-specific route contract.

Parameters such as minimum market age, baseline duration, quiet fraction and robust quantiles are versioned after inspecting forward availability distributions. They are not selected from later profitable episodes.

## 6. Trigger components

At time `T`, compare only current/earlier frames with the frozen dormant baseline.

Candidate standardized components:

- trade-intensity increase;
- quote-volume increase;
- positive signed quote-flow shift;
- effective buyer breadth/new-buyer increase;
- price or executable-recovery acceleration;
- liquidity/reserve increase or route recovery;
- reduction in trade gaps;
- cross-pool/surface consistency when multiple current surfaces exist.

Avoid a single dust transaction trigger. The first transparent version should require:

- an absolute economic-activity floor;
- plus agreement from at least two independent categories, such as flow + breadth or flow + route/liquidity;
- current data-quality validity.

The exact thresholds are registered only after current forward distribution review and before evaluating subsequent outcomes.

## 7. Manipulation-aware fields

Record, but do not automatically hard-reject unless execution is impossible:

- top-1/top-3 trade-notional share;
- effective breadth versus raw address count;
- repeated same-actor flow;
- creator/known cluster relation available at T;
- synchronized clone tokens/symbols;
- large buy followed by distributed dust buys;
- liquidity added and removed by related accounts where directly evidenced.

The strategy should learn whether Fast Escape can monetize some manipulated revivals while preserving all failures/dead cases.

## 8. Entry execution

After a valid crossing:

1. create immutable Reawakening cohort and MarketFrame;
2. evaluate all four family policies locally;
3. create shared 20 USDC amount-specific BUY/acquired-quantity SELL preflight;
4. classify executable Paper, research-only or invalid;
5. apply capital/quote-capacity and cluster selection;
6. one shared Paper fill may support the four exact entry allocations;
7. subscribe/attach the exact held surface and start exit states.

A spike that has already outrun quote freshness/deadline is a missed/late opportunity, not a later backfilled entry.

## 9. Reset and repeated episodes

After a trigger/position:

- no second episode while any same-family position is open;
- no immediate repeated crossings from the same burst;
- require activity to fall back into a newly observed dormant regime for the registered reset period;
- create a new baseline ID and new crossing;
- confirmed dead/no-reentry permanently blocks that surface/version.

A new narrative or later high price alone does not reset the episode.

## 10. Exit variants

All share the exact entry fill:

- `S09 FAST_ESCAPE`: aggressive response to failed revival, route decay and principal-recovery opportunity;
- `S10 BALANCED_DYNAMIC`: reference dynamic policy;
- `S11 PEAK_GUARD`: revival exhaustion/divergence treatment after strict current-only frames exist;
- `S12 AGENT_AUGMENTED`: exact mechanical baseline plus post-buy semantic treatment when separately active.

Reawakening exits should be especially sensitive to `failed continuation`: a burst that cannot establish a new executable-recovery high while flow/breadth/intensity revert.

## 11. Shadow and Paper denominators

Preserve:

- all valid dormant baselines;
- baselines unavailable because of data gaps;
- all crossings, including no route/late/invalid;
- portfolio not-selected reasons;
- Paper fills and all terminal outcomes;
- repeated-burst suppressions;
- new-surface versus same-surface episodes.

Do not report only famous revivals or tokens that later trended.

## 12. Outcome analysis

Compare:

- trigger-to-preflight/fill latency;
- conservative executable return at 15/60/240m and policy terminal;
- failed-continuation frequency/time;
- route recovery persistence;
- writeoff/no-route;
- capital-time;
- Fast/Peak/Agent paired differences versus Balanced;
- performance by baseline duration, dormancy depth, burst breadth, concentration and market regime;
- remove-best and cluster/date robustness.

Launch and Reawakening totals are descriptive, not directly causal, because their opportunity sets differ.

## 13. Web presentation

Show:

- baseline observed period and coverage;
- dormancy components;
- exact crossing time/components;
- pool age/surface identity;
- execution timing;
- episode number and reset lineage;
- current flow/failed-continuation state;
- all four policy outcomes.

Never display a token as Reawakening when the dormant baseline was missing or constructed after the burst.

## 14. Tests

- late trade cannot enter pre-trigger baseline/crossing;
- source gap cannot become dormancy;
- one dust trade cannot satisfy multi-component crossing;
- launch/new pool is not reawakening under the same definition;
- repeated swaps in one burst create one episode;
- a new episode requires a new observed dormant baseline;
- dead surface cannot re-enter;
- exact-identical family allocations share one entry fill;
- all no-route/late/not-selected cases remain in denominator;
- later social/price outcomes cannot create the earlier label.

## 15. Activation gate

Do not activate executable Reawakening Paper until:

- MarketFrame source and gap semantics are validated naturally;
- enough valid dormant baselines exist to set a preregistered transparent first crossing version;
- one replay/code-fixture test and one natural no-trade/quiet case show that data failure is not classified as dormancy;
- the shared execution kernel and exit priority are operational.

Until then, expose `baseline-building` and `shadow crossing` only.
