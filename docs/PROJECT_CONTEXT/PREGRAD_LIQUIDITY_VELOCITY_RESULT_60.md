# Pregraduation real reserve velocity60

REPLY_TO: C2C-20260909-PREGRAD-LIQUIDITY-VELOCITY-60
Frozen cutoff: 2026-09-09T04:16:43.166905+00:00; snapshot frontier2180780.

## Decision

**DO_NOT_REGISTER — independent holdout graduation enrichment not established after matching; postgrad economic coverage insufficient.** No new strategy, threshold, runtime change, backfill, reset or Live.

Marino et al. study graduation conditional on bonding-curve state, not guaranteed post-graduation return: https://arxiv.org/abs/2602.14860 . The local test evaluates net reserve change/sec; it does NOT measure gross inflow per trade or identify bot fragmentation. Those stronger behavioral claims were not tested.

## Frozen inputs and availability

Current exact evidence count:48944 records (47553 PREGRAD,1296 MIGRATED,95 CURVE_COMPLETE). Stage counts are records, not independent outcomes.6289 distinct first causal2-frame PREGRAD tokens;4053 training Sep5–7,1823 holdout Sep8,413 partial prospective Sep9 by evidence recorded UTC date. Across funding versions each token appears once.791 candidate records fail strict validation and do not become features; no interpolation.

Validate Pump mint-derived curve PDA, same native quote, increasing slot, both incomplete, first observed<=first recorded<second observed<=second recorded<=evidence available, after launch receipt. Recomputed real reserves/1e9 delta divided by observation interval matches stored velocity. Embedded receipt clocks and decoder/PDA evidence are not independently downloaded archival block proofs. No migration known before any frozen eligible state.

Median frame spacing30.041822s; median local-launch-to-state45.827561s. All selected states carry finite nonmissing initial quote seed (median4.938271603SOL), sourced by existing parser from PumpPortal solAmount; this is provider-reported initial transaction amount, not independent on-chain transaction verification. Missing seeds would remain missing. Selection is highly nonrandom: live watch admits only3 tokens,5min TTL, prioritized by seed/velocity. These are not population graduation probabilities.

Progress fraction is NOT reconstructible from these fields without assuming a total/target; kept null. Real reserve level is retained. Training-only positive tercile cutpoints0.010662147285033825 and0.08607686324732854SOL/sec; nonpositive separate. No nearby threshold search. See PREGRAD_VELOCITY_PREREG_60.md, written before associations.

## Migration incidence (observed, not guaranteed complete coverage)

| Split / velocity | N | Observed migrations | Within1h / matured | Within6h / matured |
|---|---:|---:|---:|---:|
| train:nonpositive | 2738 | 32 | 25/2738 | 26/2738 |
| train:positive_low | 439 | 4 | 2/439 | 4/439 |
| train:positive_mid | 438 | 17 | 17/438 | 17/438 |
| train:positive_high | 438 | 75 | 70/438 | 73/438 |
| holdout:nonpositive | 1348 | 14 | 10/1348 | 13/1220 |
| holdout:positive_low | 136 | 2 | 1/136 | 2/125 |
| holdout:positive_mid | 139 | 12 | 10/139 | 10/130 |
| holdout:positive_high | 200 | 24 | 24/200 | 21/178 |
| prospective:nonpositive | 295 | 1 | 1/239 | 0/0 |
| prospective:positive_low | 18 | 0 | 0/12 | 0/0 |
| prospective:positive_mid | 33 | 2 | 2/24 | 0/0 |
| prospective:positive_high | 67 | 8 | 8/52 | 0/0 |

Unobserved migration remains UNKNOWN; even a matured denominator only has time opportunity, not proof of exhaustive subscriptions. CURVE_COMPLETE is not automatically counted as MIGRATED. Migration labels use later token_launch_facts with valid availability clocks; no later event enters features.

Fixed reserve-level bands <10,10–30,30–60,>=60SOL: N4959/1085/210/35, observed migration25/77/59/30 respectively. Strong level dependence confounds unadjusted velocity association.

## Outcome-blind low-velocity matching

High tercile matched without replacement to nonpositive/low tercile by same UTC date/reserve band/age band; distance ranking uses reserve,age,spacing only. Unmatched remain unmatched. Matching done before outcome access.

| Split | Matched pairs | High migrations | Low migrations | Both15m endpoints | Both60m endpoints |
|---|---:|---:|---:|---:|---:|
| train | 320 | 43 | 21 | 1 | 0 |
| holdout | 162 | 13 | 13 | 0 | 0 |
| prospective | 38 | 2 | 1 | 0 | 0 |

Matched holdout13/162 vs13/162 provides no incremental graduation evidence. Only one training pair has both15m endpoints; no holdout paired endpoints. No claim of independent matched postgrad profitability is possible.

## Strict postgrad market path

Use first causal post-migration PumpSwap exact-token/pool anchor, price>0/liquidity>=1000, followed by a strictly later same-pool observation after anchor recorded within120s. Fix that entry pool for all future rows. Initial audit found6 anchors still on pump-fun and1 Meteora; clarified postgrad identity to PumpSwap only and recomputed at SAME frozen cutoff/frontier. This is a surface-correctness restriction, not an outcome-selected threshold. It can move the first anchor forward; old curve observations are never traded as migrated pools.

Training128 migrations ->99 anchors ->28 strict entries; holdout52 ->22 ->11; prospective11 ->3 ->1. Endpoint is first observation at/after15/60min within120s margin, with floor; absent invalid endpoints censored. Net return=price_exit*0.96/(price_entry*1.04)-1. MFE is maximum subsequently observed floor-eligible return, a sparse path lower bound, not a realizable peak.

| Split/high velocity | Entries | 15m endpoint N / mean net | 60m endpoint N / mean net | 60m observed paths / >=100% |
|---|---:|---:|---:|---:|
| train | 17 | 4 / -0.21558868930211164 | 1 / -0.3639273059778261 | 11 / 2 |
| holdout | 6 | 2 / -0.46002991749893674 | 0 / None | 4 / 0 |
| prospective | 0 | 0 / None | 0 / None | 0 / 0 |

High training15m endpoint mean-21.56%, median-46.87%; top1 removed sum of returns-1.878719, top3 removed-0.941254. High holdout15m2 endpoints mean-46.00%, no high holdout60m endpoint;4 observed high paths and0 >=100% right-tail. Top1 leaves-49.69%; top3 is undefined forN2. These sums are sums of fractional returns, NOT actual ledger PnL or normalized strategy performance. Full bands in result.json.

No post-entry below-floor row was observed in eligible60m paths; this does not prove no collapse. Missing data is not written off at-100%. No simulated writeoff or actual trade is invented; live positions/fills were not altered. Endpoint survivors are too sparse for valid expectancy or regime/top3 conclusions. All tokens are Solana, so cross-chain robustness is inapplicable. Date isolation fails to provide matched holdout advantage.

## Boundary and evidence

Primary bottleneck: scarce strict next/endpoint market coverage, plus selected watch and reserve-level confounding. Retain hypothesis as graduation-quality research only. No new entry until independent holdout postgrad economic evidence exists; do not lower floor/expand next-window/search velocity bins to create evidence.

Artifacts: data/research/pregrad60/frozen_features.json,matches.json,result.json,diagnostics.json. Reproducer scripts/research_pregrad60.py. Read-only source/clock/identity/recomputed-feature assertions, source-surface audit, fixed-cutoff corrected rerun; no production test/deployment needed.
