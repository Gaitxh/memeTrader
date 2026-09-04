# V5 Creator, Wallet and Participant Feature Specification

Date: 2026-09-04
Status: `P1/P2 ON-CHAIN ALPHA RESEARCH / LOCAL HISTORY LOWER BOUNDS / NO ADDRESS EXPOSURE TO AGENTS OR PUBLIC WEB`

## 1. Objective

Use only decision-time available local/on-chain history to measure whether creator and early-participant behavior improves:

- launch opportunity ranking;
- sellability/dead-risk estimation;
- flow quality/manipulation detection;
- exit timing.

Do not create “smart money” or “scammer” labels from later outcomes and backfill them into earlier decisions.

## 2. Identity levels

Keep separate:

- exact public address;
- locally stable privacy-preserving address hash for aggregates/UI/Agent inputs;
- transaction signer/payer/owner roles;
- hypothesized entity/cluster relation;
- verified current program/PDA/pool authority.

An address is not automatically a human/entity. A cluster hypothesis is versioned evidence with an availability time, not immutable truth.

Raw public addresses may remain in local restricted execution/audit tables when necessary. Public Web and Agents receive aggregate/masked/stable IDs only.

## 3. Creator features available at launch/entry

Using only prior locally recorded launches/outcomes that had matured before decision:

- prior observed launch count;
- launches in 1h/24h/7d local windows;
- time since last observed launch;
- prior migration count/rate;
- prior exact-surface route/sellability coverage;
- prior 15/60/240m conservative outcomes already matured;
- prior dead/writeoff/no-route counts/rates;
- prior liquidity survival;
- current launch initial buy/funding pattern where directly observed;
- creator/token/pool authority relationships;
- left-censor/local-history start.

Counts are lower bounds unless chain-wide history is actually queried under a registered source/version. Do not call “first launch” when local history is incomplete.

## 4. Creator behavior treatment

Creator history begins as:

- Launch Recall risk bucket;
- Flow/Reawakening context;
- dead-risk model feature;
- portfolio cluster exposure.

It is not a universal hard reject. A serial creator may produce both scams and successful fast-trading opportunities. Deterministic control/transfer impossibility remains the hard condition; economic value is tested in forward outcomes.

## 5. Early participant features

For events available by evaluation time:

- distinct payer/owner local-hash count;
- effective notional breadth;
- new versus repeat participant share under local history;
- buy/sell notional concentration;
- top-1/top-3/top-10 share;
- participant turnover and buy-then-sell timing observed so far;
- common funding/source/transaction adjacency when directly available;
- overlap with creator/pool authorities;
- local prior launches/tokens traded before the current decision;
- prior matured sellability/outcomes for those addresses/clusters.

Never use an address’s future profitable trades to mark it smart at an earlier time.

## 6. Dust/Sybil resistance

Raw unique wallet count can be manipulated. Always pair it with:

- effective breadth `(sum notional)^2 / sum(notional^2)`;
- minimum economically meaningful notional bands;
- top-k concentration;
- timing/funding similarity;
- repeat-pattern counts;
- dust share;
- source/coverage flags.

Do not collapse these into “N independent buyers”. The correct label is observed distinct addresses/effective breadth under the source/version.

## 7. Participant flow states

Potential transparent current-only states:

- `BROAD_ACCUMULATION`: positive flow with growing effective breadth/new participation and moderate concentration;
- `CONCENTRATED_BURST`: activity dominated by one/few addresses;
- `DISTRIBUTION`: early/large holders selling while new demand weakens;
- `CHURN/WASH_SUSPECTED`: high count but low net economic flow/effective breadth with repeated cycling;
- `CAPITULATION`: broad/large sell flow and route/recovery deterioration;
- `UNKNOWN/GAP`.

These are component-based research states, not accusations or legal conclusions.

## 8. Entry use

### Launch Recall

- broad/concentrated/unknown creator-wallet buckets all receive bounded Paper exploration according to capacity;
- invalid/terminal transfer/account facts still reject;
- do not wait for a rich history that arrives after the launch;
- missing history is a category, not safe/zero risk.

### Flow Acceleration

Require economic breadth/intensity agreement or explicitly classify concentrated bursts. A one-wallet large trade may still enter a scout bucket rather than being erased.

### Reawakening

Compare new participant composition with the frozen dormant baseline. Old holders distributing into many dust buyers is different from genuine new effective breadth.

## 9. Exit use

Potential early warnings:

- creator/early concentrated holders begin selling;
- top sell concentration rises;
- effective buyer breadth decays while price/recovery remains high;
- repeat/dust churn replaces new economic demand;
- common-cluster positions deteriorate together;
- route/vault/account facts worsen.

A wallet/creator warning arms a soft policy only under a registered version. Exact account/route/loss exits remain authoritative.

## 10. Historical query boundary

If direct RPC/indexer history is added:

- record query/response/source/block/time;
- freeze only data returned and available by decision;
- distinguish full-chain coverage from local lower bound;
- preserve rate limits/errors/truncation;
- do not query current history later and pretend it was known at launch;
- do not store/expose unnecessary private or unrelated wallet data.

Prefer maintained legal indexer/RPC methods only after local event history coverage is measured insufficient for the hypothesis.

## 11. Cluster construction

Potential links:

- direct transfer/funding adjacency;
- common signer/authority;
- shared initial transaction/block pattern;
- repeated synchronized launches/trades;
- exact source/metadata/website relation;
- common pool/LP control.

Each edge has evidence IDs, availability time, confidence and version. Cluster IDs are current projections; decisions reference the exact cluster revision available then. Later clustering cannot rewrite earlier exposure.

## 12. Labels and leakage prevention

Allowed later labels for model research:

- time-to-economic exit/no-route/dead;
- conservative terminal PNL;
- liquidity survival;
- creator’s subsequent launches only for decisions after they occur;
- participant’s prior outcomes only if matured before the new decision.

Forbidden earlier features:

- current full wallet history fetched months later;
- final token ATH/market cap;
- later exchange listing/current holder count;
- address labeled smart/scammer from this same token’s future path;
- cluster relation discovered after decision without availability clock.

## 13. Storage and privacy

- local restricted mapping from raw address to stable hash only when needed;
- public APIs return masked/hash aggregates;
- Agents receive no raw wallet list unless a narrowly reviewed public-evidence task requires one; default is aggregate facts;
- no private keys, wallet sessions or unrelated wallet assets;
- retain decision-linked aggregate components and source references;
- high-volume raw participant events follow MarketFrame retention rules.

## 14. Economic evaluation

For creator/participant buckets report:

- candidate/fill counts and independent creators/clusters/dates;
- sellability/dead/writeoff;
- conservative PNL/median/tail;
- Fast versus Balanced/Peak outcomes;
- capital-time and quote load;
- concentration/winner removal;
- missing/left-censored group.

Do not conclude a creator/wallet feature is useful from raw price return alone.

## 15. Model path

Start transparent. Later candidates:

- hierarchical/shrinkage creator effect on sellability/dead risk;
- participant breadth/concentration hazard features;
- graph/cluster summaries learned only from training history;
- calibrated return/tail models.

High-cardinality address IDs should not enter a model as memorized categorical winners unless leakage/generalization controls are explicit. Prefer behavior summaries.

## 16. Tests

- later launch/outcome cannot alter earlier creator features;
- local-history count marked lower bound/left-censored;
- raw wallet count and effective breadth differ under dust wallets;
- same-address repeat events dedupe correctly;
- cluster revision after decision does not rewrite decision exposure;
- creator/participant risk is not universal hard reject;
- exact account/transfer hard facts override positive wallet score;
- public Web/Agent output contains no raw sensitive wallet material;
- no source error/truncation becomes zero risk;
- same token’s future profit cannot label its entry wallet smart.

## 17. Integration order

1. reuse current creator-launch-risk and holder-breadth forward ledgers;
2. add transaction-derived effective breadth/concentration to MarketFrame;
3. expose risk buckets/advisory states;
4. evaluate future outcomes;
5. add only one creator/participant challenger at a time;
6. fitted graph/wallet models remain later research.
