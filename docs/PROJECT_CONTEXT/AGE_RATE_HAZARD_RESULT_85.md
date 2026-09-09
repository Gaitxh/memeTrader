# Age-rate entry hazard audit85

REPLY_TO: C2C-20260909-AGE-RATE-HAZARD-85
Disposition: NO_ROBUST_VETO; RESEARCH_ONLY; deployed parent unchanged.

## Frozen evidence and accounting

Cutoff 2026-09-09T07:43:27.226029Z; snapshot frontier2252941; trade frontier511933; current funding-20260906-v002-final-1000, resource_age_rate_candidate_v1. Read-only transaction completed in1.424s with a25s query progress ceiling. An initial schema-name error ended before any freeze artifact; corrected source_observed_at and froze once. All subsequent computation reads frozen.json only. No production update/restart, parameter search, model fitting or new registration.

153 actual terminal positions,152 unique tokens,0 open/censored at cutoff. Each BUY cash cost5U; trade cash/PnL, position PnL and quantity*execution price reconcile with zero discrepancies. Features use the recorded entry snapshot (all153 pass exact chain/base/pool and observed<=ingested<=recorded<=opened_at), not later marks or mutable token metadata. Past frames must share exact pool, be available before entry and strictly precede it by observed>prior recorded; max120s gap. Solana identity is case-sensitive.47 histories reached the bounded128-row retrieval cap; closest valid pairs exist for all153, third-frame acceleration is UNKNOWN for21. This is not full historical path reconstruction.

Raw entry buys/sells are genuinely present for153/153, zero both for0; missing is never converted to0. Native facts are filtered by their own three clocks and entry availability. ASOF_LAUNCH_FACT identifies50 positions with PumpPortal facts only; it is not native economic viability or a cross-venue safety score. All153 entries are Dex source and growth15m-6h; therefore provider/age strata cannot discriminate within this deployed selection.

The two positions overlapping19:06-19:51:47Z Sep8 are explicitly source-confounded. Full ledger remains reported; clean151 PnL+562.5306U versus full+559.9705U. No catastrophic terminal belongs to that known storm subset. Other unknown engineering contamination has not been ruled out by this entry-feature audit.

## Distribution

- Net PnL+559.9705U;42/153 winners; median-.40276U (-8.055% of stake), mean+3.65994U (+73.199%),10%-trimmed mean-.44271U. Trimming removes15 observations from each end.
- Positive profit711.9046U; negative loss151.9341U. Catastrophe is frozen as net return<=-50% of actual BUY cost:17 positions lose77.6659U. This is distinct from a generic hard stop or writeoff.
-12 positions with net return>=+100% contribute676.8065U,95.07% of positive profit. Top1/top3 positive-profit concentrations14.94%/41.93%; removing top1/top3 leaves+453.6287/+261.5006U. Grouping repeated positions by token gives the same top-removal totals. This current cutoff supersedes any older claim that top3 removal necessarily makes this parent negative; it does not establish stable Alpha.

|Actual terminal reason|N|Net PnL U|
|---|---:|---:|
|Max hold|75|659.2069|
|Hard stop|57|-120.0020|
|Trailing|19|30.7655|
|Liquidity-floor writeoff|2|-10.0000|

Fifteen catastrophes occur via hard-stop executions, including near-total loss, and two via explicit floor writeoff. Thus counting only writeoffs materially understates catastrophic realized losses. These are existing simulated ledger executions, not proof of actual onchain fillability.

## Frozen broad strata: what a veto would remove and sacrifice

Catastrophe dollars removed means the absolute realized loss of selected <=-50% positions. Positive/tail dollars sacrificed includes every positive/ >=100% return position in the same stratum. Veto net change is minus the stratum's observed total PnL, assuming other historical fills unchanged; it is an accounting deletion, not a rerun of capital allocation or a validated counterfactual strategy. Rows overlap and must NOT be added together. No bin boundary was optimized.

|Veto stratum|N|Catastrophe U removed|Positive U sacrificed|Tail U sacrificed|Net U change|
|---|---:|---:|---:|---:|---:|
|chain=bsc|50|16.683|668.746|659.264|-624.253|
|chain=robinhood|45|2.885|27.211|6.651|+5.680|
|chain=solana|58|58.098|15.947|10.891|+58.603|
|date=2026-09-07|36|7.885|31.281|13.144|-2.878|
|date=2026-09-08|101|69.781|402.769|389.179|-281.826|
|date=2026-09-09|16|0.000|277.855|274.484|-275.267|
|provider=dexscreener|153|77.666|711.905|676.806|-559.970|
|age=GROWTH_15M_6H|153|77.666|711.905|676.806|-559.970|
|liquidity=10K_100K|85|14.568|695.598|665.916|-631.018|
|liquidity=GE100K|40|54.991|13.207|10.891|+50.785|
|liquidity=LT10K|28|8.107|3.100|0.000|+20.262|
|buy_share=50_75|79|57.876|38.921|24.035|+60.355|
|buy_share=75_90|25|3.152|663.017|652.772|-653.269|
|buy_share=GE90|9|10.000|2.043|0.000|+11.766|
|buy_share=LT50|40|6.638|7.924|0.000|+21.177|
|turnover=1_10|26|11.037|658.846|652.772|-636.606|
|turnover=GE10|8|3.107|0.000|0.000|+6.226|
|turnover=LT1|119|63.522|53.059|24.035|+70.409|
|entry_continuation=DOWN|8|0.000|2.425|0.000|+1.632|
|entry_continuation=FLAT|115|52.669|530.395|507.592|-418.445|
|entry_continuation=UP|30|24.997|179.085|169.214|-143.158|
|liquidity_growth=DOWN|11|0.000|63.816|61.322|-59.393|
|liquidity_growth=FLAT|108|52.669|468.043|446.270|-360.714|
|liquidity_growth=UP|34|24.997|180.045|169.214|-139.864|
|rolling_count_acceleration=DOWN|81|47.878|202.809|184.419|-116.189|
|rolling_count_acceleration=FLAT|38|19.789|177.018|171.786|-137.914|
|rolling_count_acceleration=UNKNOWN|21|0.000|258.830|249.778|-246.707|
|rolling_count_acceleration=UP|13|9.999|73.249|70.824|-59.160|
|source_continuity=SAME|153|77.666|711.905|676.806|-559.970|
|raw_activity=KNOWN|153|77.666|711.905|676.806|-559.970|
|native_provenance=ASOF_LAUNCH_FACT|50|58.098|13.370|10.891|+56.343|
|native_provenance=UNKNOWN|103|19.568|698.535|665.916|-616.314|
|source_period=CLEAN|151|77.666|711.905|676.806|-562.531|
|source_period=STORM_CONFOUNDED|2|0.000|0.000|0.000|+2.560|

## Why no robust veto is promoted

1. **Liquidity>=100k is a regime proxy, not demonstrated universal safety.** It removes54.991U catastrophic losses and sacrifices13.207U positives, but all11 catastrophes are Sep8 Solana;35/40 positions are Solana. Sep9 the same stratum has9 positions/+8.968U, including10.891U tail profit and no catastrophe. A pooled benefit reverses on the next date.
2. **Liquidity<10k is the most consistent descriptive weak group, not a confirmed catastrophe veto.**28 positions net-20.262U across three negative dates/chains; hypothetical veto removes8.107U catastrophe and sacrifices3.100U positive profit, no observed tail. Yet catastrophic evidence is only2 tokens on Sep8; Sep9 has only2 positions. This warrants a frozen prospective hypothesis, not a conclusion that the rare paying tail is absent. No gate is installed.
3. **Volume/liquidity>=10 has no winner in8 observations**, but all are Solana and7/8 Sep8. It fails cross-chain evidence. Conversely vetoing turnover<1 removes63.522U catastrophe but sacrifices53.059U positives/24.035U tails, with date-level net sign reversing: Sep7+5.123U, Sep8-87.206U, Sep9+11.674U.
4. **Buy-share gates also mix opportunity and regime.** >=90% has9 samples across two dates, removes10U catastrophic losses but sacrifices2.043U profit; Robinhood subset is positive. <50% and50-75% pooled losses reverse on Sep9.75-90% holds most BSC tails; this is not an independently validated universal safe zone.
5. **Immediate liquidity/price direction does not cleanly avoid losses.** Increasing liquidity contains24.997U catastrophes but180.045U positive profit; declining liquidity has63.816U positives and no observed catastrophe in11 rows. A reflexive 'liquidity decreasing=>veto' would cut one61.322U tail.115/153 entry price comparisons are FLAT; rolling data often carries little new short-path information.
6. **Activity acceleration is a rolling-count derivative, not fresh trade arrival velocity.** Overlapping5m counts can fall when trades age out. Down/flat/up all sacrifice large positive profit; UNKNOWN21 contains258.830U positive profit. Missing trajectory must not become an automatic veto. No claims about wallet/manipulation risk can be derived from these counts.
7. **Chain/native selection would bake in the observed regime.** BSC50 positions+624.253U, RH45 -5.680U, SOL58 -58.603U. Native-present is50 Solana positions, not a causal hazard proof. Dates Sep7+2.878U, Sep8+281.826U, Sep9+275.267U; current profit is not exclusively a Sep8 jackpot, but the paying tail remains heavily BSC-concentrated. Entry source/age are invariant by selection and cannot justify a new veto.

The JSON artifact contains date, chain, joint chain/date and known-storm-clean breakdowns for EVERY fixed stratum. There is no adequately replicated Pareto separation across time and chain that preserves the paying tail. Keep resource_age_rate_candidate_v1 unchanged. The champion comparison rule77 continues to apply to any future challenger; this study does not reopen the paused15m/60m pair.

## Today23 diagnostics only

At this cutoff the parent captures the same five user-case identities: DUO-.79115U(maxhold), PARLEY-1.07688U(hardstop), RECEIPT+1.86011U(trailing), GME20-1.49291U(hardstop), PYRE+.55849U(maxhold), total-0.94235U. These selected strong-riser examples are neither validation nor the full parent result; the large parent tails lie elsewhere. No case address enters a feature/gate.

## Artifacts and validation

- data/research/age_rate_hazard85/preregistered.json: fixed definitions before extraction.
- frozen.json: positions/trades/entry and bounded prior rows/native facts, cutoff and frontiers; no writes to production.
- result.json: position-level exact pointers, costs/returns/known inputs, all veto tables and case diagnostics.
- scripts/research_age_rate_hazard85.py: reruns analysis from existing freeze without rescanning production.
- Three targeted tests pass: causal identity/clocks/missingness, tail-sacrifice/censored accounting, exact fixed bins. Actual153 position/trade/entry-quantity reconciliation discrepancies0. No performance backtest, threshold fitting or strategy mutation.
