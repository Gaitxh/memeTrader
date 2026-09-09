# First-hit order75 — sampled order, not chart-peak eligibility

Reply C2C-20260909-EXECUTABLE-FIRST-HIT-75. Used only completed local research SQLite/universe71 and fixed74 medians; **no production rescan or runtime/strategy change**. Same cutoff2026-09-09T04:55:14.116134Z/frontier2194123. Sep7 exploration,Sep8 unchanged holdout.

## Definition and coverage boundaries

Original locally first-valid exact pool, strictly later entry after anchor recording; walk in receipt/ID order and require each new observation after prior accepted recording. Costs4%buy/4%sell. Record first sampled <=-20%,>=+30%,>=+100% within60m. Once an inter-frame gap exceeds the existing120s continuity bound before the competing first hit, order is UNKNOWN_GAP. Keep no-entry and no-observed-hit separately; neither is a negative label. Also retain unqualified sampled order for comparison. Even <=120s sampling cannot prove that no intervening threshold crossed.

**Liquidity-floor first-hit is UNKNOWN for every row**: normalized71 deliberately retained only liquidity>=1000. Its omitted low-floor rows cannot be recovered under this task's no-production-rescan constraint. Consequently this study cannot certify executable first-hit probabilities; it supplies sampled price order conditional on retained evidence. It does not invent zero floor failures.

## First-hit results

| Date | Anchors / strict entries | +30 first / -20 first / gap-unknown | P(+30 first), competing observed subset | +100 first / -20 first / gap-unknown | P(+100 first), competing observed subset |
|---|---|---|---|---|---|
| Sep7 |21773 /7513|296 /266 /84|52.67% (562 rows)|86 /321 /70|21.13% (407 rows)|
| Sep8 |24748 /9380|253 /239 /292|51.42% (492 rows)|79 /275 /193|22.32% (354 rows)|

Sep8 additionally8596 entries have no observed competing30/-20 hit;8833 have no observed100/-20 hit. Fractions on the **full strict-entry denominator** are253/9380=2.70% and79/9380=0.84%; these are observed-positive incidence, not true success probabilities with unknowns scored as failures. The subset probabilities above must not be used as an all-token precision claim.

Ignoring gaps, Sep8 sampled+100-first is154 and stop-first393.182 sampled paths ever hit+100:28 already hit stop first;75 of the154 positive-first paths cross a >120s gap before the first event, leaving79 continuity-qualified sampled positives. This is the direct correction to MFE-only interpretation. For Sep7:125 ever hit100,103 sampled positive-first,22 stop-first,86 continuity-qualified positives.

First-hit seconds from entry (all observed crossings, including gap-affected; not survival estimates):

| Date | -20 median /P90 | +30 median /P90 | +100 median /P90 |
|---|---|---|---|
| Sep7 |178.23 /931.36|212.72 /887.87|387.21 /1954.44|
| Sep8 |253.40 /2083.02|389.28 /1613.79|741.47 /1914.13|

## As-of diagnostics

Anchor activity-rate,buy-share,turnover use the already frozen71 Sep7 median. Third-frame diagnostics use unchanged74 medians, but **execute at a fourth strictly later frame** before labeling; third-frame features never classify the earlier second-frame entry. Complete threeframe cohorts2468/2885 yield fourth entries1286/1658. For Sep8 only60 positive30-first vs110 stop-first and18 positive100-first vs129 stop-first remain continuity-qualified; unknowns dominate.

High activity/turnover and high third-frame volume/liquidity continue to enrich stops as well as opportunity. One tentative hazard clue: high **anchor buy-share** has Sep7 positive30/stop counts135/72 in9192 anchors, versus160/191 in11133 low; Sep8 high127/72 in11013 versus113/145 in11211 low. Positive30 incidence high/low is1.47%/1.44% then1.15%/1.01%; stop-first incidence.78%/1.72% then.65%/1.29%. This merits prospective discrimination research, not a rule registration.

It does not establish uniform conditional improvement: BSC/Gecko high-vs-low positive30 incidence falls from8.42% to4.22% onSep7 and7.65% to2.90% onSep8 while stop hazard also falls. Solana/Gecko Sep8 high increases positive incidence but slightly increases stop incidence. Provider/chain composition and missing paths matter. All fixed feature-bin strata are retained in result.json, not just favorable ones. Anchor raw missingness outside74's audited frame set remains an additional caveat.

## Research-only fast replay

Sampled net hard stop-20%, trailing activation+30% with15% running-price drawdown,15m max-hold; trigger on current causal frame and settle only on the next causal frame. No peak-timed sells. Gap-affected or missing trigger/fill paths UNKNOWN. This is an explicit next-frame model, not a bit-identical replay of every production exit path; missing low-floor evidence prevents that claim.

Baseline selected next-frame fills486/475: median returns-7.69%/-7.12%. These small coverage-selected subsets are not all-universe PnL estimates or guaranteed lower bounds on realized profit. Third-frame Sep7 replay mean is unusable: one retained price discontinuity dominates (`bsc:0xb54d4c52e6f127cab6f96e4cf96128772d524444`,entry1661359,hard-stop signal1661763,next frame1662210,net518958.27x). Top1 removal sum=-11.690 andtop3=-18.034 across remaining return observations. Preserved, not silently filtered or called alpha. Source validation of that discontinuity would require separately authorized source evidence beyond this frozen input.

Disposition: **NO_STRATEGY_REGISTRATION; FIRST_HIT_PRICE_ORDER_AVAILABLE_WITH_FLOOR_AND_GAP_LIMITATIONS**. A future strategy must prove positive-first path ordering and causal sell availability, not merely later MFE. Three deterministic tests passed: stop-then-moon, positive30-then-stop-before100, gap/cache-clock rejection. Artifacts `data/research/first_hit75/{result,rows,run_summary}.json`; script `research_first_hit75.py`.
