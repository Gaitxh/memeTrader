# Pure-On-Chain Meme Strategy Universe and Prioritization

Date: 2026-09-04
Status: `RESEARCH UNIVERSE / ONLY EXPLICITLY PROMOTED ITEMS ALTER THE ACTIVE DAG`

## 1. Selection criteria

Each strategy idea is judged on:

- economic mechanism, not correlation name;
- point-in-time data availability;
- amount-specific executable entry/exit support;
- expected edge after high turnover cost;
- rug/no-route/tail exposure;
- sample opportunity and independence;
- current code/data readiness;
- latency and provider/storage cost;
- overlap with existing entry families;
- displacement cost from Gates A-C and current exits.

Statuses:

- `PROMOTE_V5`: active v5 family;
- `SUBCOHORT/FEATURE`: preserve inside an active family, not a separate account now;
- `SHADOW_LATER`: valuable after dependencies;
- `RESEARCH_ONLY`: measure but do not simulate an executable fill yet;
- `REJECT_CURRENT`: mechanism/data/execution is too weak or misleading now.

## 2. Prioritized universe

| Idea | Economic mechanism | Point-in-time data | Main risk | Current disposition |
|---|---|---|---|---|
| Launch Recall | Large supply of very early launches creates a heavy-tailed payoff; broad bounded sampling may capture rare winners and measure gate opportunity cost | create/migration, mint, current route/preflight, current market facts | high dead/manipulation/turnover tail | `PROMOTE_V5` |
| Flow Acceleration | Persistent broad net demand and improving executable depth may continue after a current flow crossing | PumpSwap trades/vaults, effective breadth, route/recovery | one-wallet/wash bursts and late entry | `PROMOTE_V5`, feature pending |
| Reawakening | A genuinely dormant old market may reprice when new broad demand/liquidity returns | pre-trigger dormant baseline + new flow/route crossing | retrospective label/data gap mistaken for dormancy | `PROMOTE_V5`, baseline building |
| Migration Impulse | Bonding-curve graduation/migration may create a short repricing/liquidity-discovery interval | exact migration event, pool facts, first AMM flow, route | extreme crowding/latency; overlaps Launch | `SUBCOHORT` of Launch/Flow, analyze separately |
| Canonical vs noncanonical surface | Canonical protocol-owned liquidity may reduce structural tail; noncanonical/opaque may offer more opportunities but higher risk | current surface/route/mint facts | missing exact watcher or creator-controlled liquidity | `SUBCOHORT/FEATURE`, not a standalone alpha claim |
| Immediate recovery quality | Better current round-trip recovery reduces cost hurdle and often signals depth | exact BUY→acquired SELL preflight | may select already-mature/late tokens; not alpha alone | `FEATURE/RISK BUCKET` |
| Sellability recovery | A token currently/no-recently no-route may regain a route/liquidity and start a new opportunity | immutable no-route history + current route recovery + surface episode | false transient provider recovery; stale/old exposure | `SHADOW_LATER`, possibly Reawakening component |
| Liquidity-add impulse | New genuine liquidity may reduce impact and attract demand | exact vault/LP/pool event + route | creator adds removable bait liquidity | `SHADOW_LATER` inside Flow/Reawakening |
| Failed-continuation escape | A burst that loses flow/breadth/route quality should be exited quickly | current MarketFrames and executable recovery | overreacting to noise; quote cadence bias | `EXIT FEATURE` for Fast/Peak |
| Creator-history risk/edge | Repeat launch behavior and prior matured outcomes may predict sellability/tail or operational skill | local prior launches/outcomes available before decision | address rotation, left censoring, memorization | `FEATURE`, not standalone strategy initially |
| Early participant breadth | Broad economic participation may be more durable than one-wallet pumping | transaction-derived effective breadth/concentration | Sybil/dust/wallet≠human | `FEATURE` for Flow/Peak/risk buckets |
| Early holder distribution | Supply concentration and its change may affect dump risk | current RPC/indexer/account facts | pool/custody/dust misclassification, latency | `SHADOW FEATURE`; no hard gate until validated |
| Wallet-cluster following | Prior successful/fast participants may repeat behavior | only prior matured local outcomes and current activity | severe selection/future leakage and identity rotation | `SHADOW_LATER`; behavior summaries only |
| Creator/insider distribution exit | Creator/early concentrated sells may precede demand exhaustion | current participant role/flow/account facts | incomplete identity; ordinary sells misread | `EXIT FEATURE`, advisory first |
| Route-quality acceleration | Improving minimum recovery/price impact/route simplicity may precede tradability | repeated amount-specific quotes | provider sampling cost/endogeneity | `FEATURE`; bounded cadence |
| Cross-surface price/route dislocation | Different venues/routes may temporarily price the same mint differently | simultaneous amount-specific routes and balances | no atomicity, fees, route changes, inventory | `RESEARCH_ONLY`; not current directional v5 |
| Cross-chain meme replication | A narrative/token archetype may launch on BSC/Robinhood after Solana | chain discovery + exact identity + chain execution | clone ambiguity, chain-specific cost/safety | `SHADOW_LATER` after adapters |
| Information-first event trade | Timely independent event evidence may precede price | exact local event/token binding and current route | current low conversion/high Agent cost, clone fanout | `PRESERVE MAINTENANCE`, not v5 active family |
| Post-buy narrative runner | New independent information after entry may justify longer holding | shared bounded case/result after entry | confirmation bias/latency | `AGENT_AUGMENTED` treatment, advisory first |
| Boost/trending-list entry | Paid visibility may create short demand | provider boost/list status and current route | promotion/manipulation/conflict; survivor bias | `REJECT_CURRENT` as evidence; audit feature only |
| Raw volume/momentum threshold | Strong provider 5m momentum may persist | Dex aggregates | wash, lag, no execution truth | immutable control/feature, not standalone final strategy |
| Dip-buy after collapse | Mean reversion after sharp fall | current price/flow/route | often rug/distribution; no clear floor | `REJECT_CURRENT` executable strategy; outcome research only |
| Pure inactivity/flat-price buy | Quiet token may awaken | provider flat/zero volume | stale data/dead pool, no trigger mechanism | `REJECT_CURRENT`; requires Reawakening baseline/crossing |
| “Smart money” static label copy | Follow addresses labeled profitable | current vendor/current wallet label | future leakage, address rotation, crowding | `REJECT_CURRENT`; rebuild strict prior behavior if studied |
| Historical ATH/market-cap pattern | Winners share early path features | full path | direct future/survivor leakage | `REJECT` as decision input |
| LLM numeric buy/sell prediction | Semantic model predicts price/position | text/context | hallucination, latency, no calibrated execution | `REJECT`; LLM only structured semantic advisory |
| MEV/backrun/bundle strategy | Extract value around launches/swaps | mempool/leader/bundle access | adversarial infrastructure, capital, landing/reorg/security | `PRESERVE SEPARATE FUTURE PROJECT`, not v5 directional path |
| Cross-DEX atomic arbitrage | Capture simultaneous route imbalance | executable atomic transaction/build/simulation | requires inventory/atomic routing/fees/competition | `PRESERVE SEPARATE`, not current Paper abstraction |

## 3. Why Launch, Flow and Reawakening are the first three

They span materially different opportunity clocks:

- **Launch**: first availability of a new market/token;
- **Flow**: current acceleration in an active market;
- **Reawakening**: regime change after an observed dormant baseline.

They can share the same execution/risk/learning kernel while keeping denominators distinct. They also match the user’s key goals:

- more early trades/opportunities;
- current-only dynamic alpha;
- old tokens that suddenly move.

Adding more active families before these work would divide scarce forward samples and implementation attention.

## 4. Candidate subcohorts for current data collection

Record without creating more accounts:

- exact create versus migration versus first AMM trade;
- canonical/noncanonical/opaque surface;
- immediate recovery/liquidity/momentum bands;
- creator-history bands;
- broad versus concentrated participant flow;
- route recovery versus continuously available;
- with/without exact pool monitoring;
- market congestion/time regime;
- passive information/narrative available before/after entry.

These support later challenger decisions and explain heterogeneity.

## 5. Strategy idea promotion template

A future candidate must state:

1. causal/economic mechanism;
2. exact cohort/trigger and available-at clocks;
3. complete opportunity denominator;
4. execution amount/cost/route semantics;
5. expected failure/tail mechanism;
6. current data/code readiness;
7. one primary comparison and outcome;
8. minimum maturity/stop gate;
9. overlap/displacement cost;
10. `PROMOTE_NOW / NEXT_CYCLE / PRESERVE / REJECT`.

A compelling chart or famous token is not sufficient.

## 6. Next-cycle shortlist after current v5 core

Subject to new forward evidence:

1. Migration Impulse as a registered Launch subpolicy only if exact migration-to-route latency/flow differs economically from generic Launch;
2. Sellability Recovery/Reawakening route-recovery challenger;
3. creator/participant risk-adjusted ranking feature;
4. liquidity-add plus broad-flow trigger;
5. cross-chain replication only after BSC/Robinhood execution truth.

No shortlist item interrupts Gates A-C or existing v4 exits.
