# Path-shape hazard101 — bounded validation, no deployment

REPLY_TO: C2C-20260909-PATH-SHAPE-HAZARD-101

Disposition: INSUFFICIENT_EVIDENCE / DO_NOT_DEPLOY_SHADOW. Regular rising price is not established scam evidence. The conditional deployment gate did not pass; no funded strategy, global veto, runtime change, restart, provider request or source-data mutation.

## New Lead evidence — C2C-20260909-PATH-SHAPE-101-EVIDENCE

Received after the initial result. Status: LEAD_REPORTED / NOT_INDEPENDENTLY_REPRODUCED. The message provides aggregate results but no frozen cutoff, position/snapshot row pointers, executable query or exact regression definition. Preserve these findings separately; they do not overwrite the original frozen-universe result or establish a deployable gate.

- Universe reported: 166 terminal resource_age_rate_candidate_v1 positions; exact original-pool snapshots in the 10 minutes before actual entry, >=6 frames required. Coverage-matched >=20-frame subset: other39, hardstop17, severe7, tail>=100%2. Label precedence/overlap is not provided; do not assume these are disjoint or infer the subset denominator by summation.
- Median R2: tail>=100% .278 versus hardstop .667.
- Exploratory LINEAR_UP: gain>=10%, R2>=.80, non-down-step fraction>=.85; 5 hits, all hard-stop, aggregate actual PnL -6.37U, no tail>=100%.
- Exploratory STAIRCASE: >=20 frames, gain>=5%, plateau fraction>=.65, top3 positive steps>=75% of positive log move; 12 hits:7 hardstop/1 severe/4 other, -15.15U, no tail>=100%.
- Smooth-any: R2>=.8 and non-down fraction>=.85; 9 hits:6 hardstop/3 other, -7.88U. Groups can overlap; do not add their losses or describe them as counterfactually recovered PnL.

Interpretation: this raises the priority of dense pre-entry shape falsification. It is selected actual age-rate evidence, not an all-market validation set. Only two coverage-matched tails cannot establish preservation of the strategy's paying right tail. Actual terminal exit reasons differ from the earlier sampled first-hit labels. Non-down fraction differs from strictly-up fraction; plateau/top-step definition and R2 estimator also differ from the frozen101 design. None of the newly reported cutoffs replaces the existing frozen bins or becomes a tuned veto.

Next bounded evidence step: obtain/freeze the diagnostic row pointers and definitions, verify every feature row was locally recorded before entry (not merely observed before it), unique opportunity/duplicate-contamination handling, original-pool identity, sampling/cache generations, label overlap and time/chain/provider composition. Reuse the existing offline universe for unchanged-definition falsification; keep any newly explored shape variant explicitly separate from prior holdout validation. Report tail-profit/positive-first sacrifice alongside hazard enrichment and UNKNOWN coverage. Prospective unfunded Shadow is prioritized for reconsideration only after that evidence check; it is not enabled by this aggregate message. Price shape remains separate from flow regularity and authenticated synthetic-support evidence. No historical mutation, new runtime collector, trading gate or funded arm in this acknowledgment.

## Frozen causal design

Reused universe71 offline `normalized_identity.sqlite3`: 929,595 valid rows, frontier2194123, cutoff2026-09-09T04:55:14.116134Z. Sep7 exploration; Sep8 holdout. Unit=unique token plus first locally valid exact pool, not proof of first onchain pool. Original normalization verifies token/pool identity and observed<=ingested<=recorded, positive price, liquidity>=1000. Later same-pool provider transitions may supply outcomes, not the feature window.

Before inspecting outcomes the script fixed: first8 strictly causal frames (each observed after previous recorded), one provider, >=60s observed span, <=900s availability span, adjacent gap<=120s. Feature cutoff is eighth recorded time. Research entry is the ninth independent original-pool frame within120s; no ninth frame remains UNKNOWN. Never label the earlier entry using later shape. Outcomes at15/60/240m use the 4% buy/4% sell price proxy, endpoint tolerance+120s, and strictly causal frame sequence. First observed +30 versus -20 is separately recorded; >120s preceding gaps make order UNKNOWN. These are sampled research returns, not actual strategy fills or executable continuous paths.

Features: Theil-Sen log-price/time slope; its residual SSE R2 (may be negative; flat path R2 UNKNOWN), residual MAD, strictly-up fraction, plateau fraction, plateau+jump score, jump interval/size CV, liquidity/price log correlation and endpoint elasticity, liquidity retention, price displacement per mean reported5m volume/transaction count, final buy-count share and volume/liquidity. Overlapping5m aggregates are NOT incremental notional or unique-wallet breadth. Explicit zero denominators remain unavailable ratios, not zero-valued evidence.

Fixed descriptive labels, not scam thresholds: LINEAR_RATCHET requires positive displacement, R2>=.9 and up fraction>=.85; STAIRCASE_RATCHET requires positive displacement, >=2 of7 increments within0.1%, >=3 jumps of1%, no downstep beyond0.1%; remaining measured paths NORMAL. NORMAL means only neither shape label, not safe. No threshold grid. Continuous diagnostic splits use Sep7 medians unchanged on Sep8; a zero staircase median yields an empty low bin and is explicitly non-informative, not repaired by searching a cutoff. Feature-negative/insufficient paths are not called NORMAL in the full denominator.

## Coverage and primary findings

46,521 original anchors ->443 feature episodes (0.95%):235 Sep7 /208 Sep8.44,534 lacked8 strict frames;1,212 failed span/gap;332 changed provider. Density selection is substantial, so results cannot estimate all-market scam precision.

| Date / shape | Feature N | 60m visible paths | Observed >=100% | Observed <=-50% | 60m endpoints |
|---|---:|---:|---:|---:|---:|
| Sep7 NORMAL |217|190|23|42|23|
| Sep7 LINEAR_RATCHET |8|4|0|0|0|
| Sep7 STAIRCASE_RATCHET |10|9|3|2|4|
| Sep8 NORMAL |202|192|14|33|29|
| Sep8 LINEAR_RATCHET |1|0|UNKNOWN|UNKNOWN|0|
| Sep8 STAIRCASE_RATCHET |5|5|0|2|0|

The5 holdout staircases have40% observed severe-loss incidence versus17.19% NORMAL, but no60m endpoint and no cross-date tail-preservation replication. Sep7 staircases include3 observed doubles (all Robinhood); discarding them would remove those opportunities. Removing top3 tail tokens leaves0 staircase tails: tiny, tail-concentrated evidence. Sep8 staircase composition is1 BSC (loss) +4 RH (one loss); no Solana case. Every LINEAR_RATCHET is BSC/Gecko and holdout has no strict entry. Source/cache sampling may itself create apparent plateaus; this study cannot attribute intentional manipulation.

The monotonic-up diagnostic split (Sep7 median1/7, so this broad bin is NOT the extreme-ratchet label) shows the danger of a universal filter:

| Date / split | Visible60m paths | Tails | Severe losses | Known +30-first / -20-first |
|---|---:|---:|---:|---:|
| Sep7 low |67|5|4|6 /3|
| Sep7 high |136|21|40|31 /60|
| Sep8 low |80|1|1|1 /5|
| Sep8 high |117|13|34|22 /42|

Vetoing high monotonicity would discard34/35 observed holdout severe-loss paths AND13/14 observed doubles, plus22 of23 known positive-first paths. Tail and loss labels overlap; these counts are not avoided-loss dollars or recovered PnL. R2 alone also fails replication: high versus low observed severe-loss rates16.67% vs40.26% on Sep7,27.66% vs26.19% on Sep8. No claim of a stable hazard classifier is justified. Liquidity retention and notional proxies show opportunity/hazard tradeoffs, not a supported combination. Full bins and chain/provider strata are preserved rather than selecting only attractive results.

## Missingness, vault and resource boundary

443 feature episodes /3,544 raw snapshot IDs were audited using exact INTEGER PRIMARY KEY reads (<=200 IDs/batch), not a production snapshot scan. All443 have explicit numeric volume/buy/sell aggregates;3,592 explicitly zero fields among them. Ratios preserve zero-denominator UNKNOWN. Warm run source-read time0.128s. This does not authenticate reported volume or count distinct traders.

Existing vault `REGULARITY_PATTERN` measures trade interval/size regularity; `SYNTHETIC_SUPPORT_PATTERN` additionally uses alternation, narrow implied-price variation and turnover; unwind uses reserve/depth deterioration. Price linearity is a different signal. Bounded lookups across5 existing vault registrations for97 Solana feature identities (485 unique-key pool lookups) found0 exact targets. Thus concentration/alternation/size-regularity combination is UNKNOWN; no SYNTHETIC_SUPPORT_COMBINED assertion. No new index, observer or collection requests were added. Join took0.019s. The user-supplied support_risk183-terminal totals remain context, not independently recomputed evidence for this shape experiment.

The frozen normalized input excluded below-floor frames; actual liquidity writeoff cannot be inferred from absence. Hard-stop here means observed costed -20 crossing, not a ledger exit reason. First-hit gaps and endpoint censoring remain UNKNOWN. Actual writeoff-linked calibration and dense price/amountful overlap are concrete missing evidence, not a reason to lower the floor or increase collection budgets.

Total warm research run8.50s against the offline indexed333MB research database; no live full scan.6 focused tests PASS (linear/flat/staircase math, availability equality, stop-then-moon overlap, gap/censoring, no contemporaneous outcome). Script rerun after bounded vault join succeeded. Production strategy/safety/watch/request semantics and Live lock untouched; no new claim about current runtime latency is made.

## Falsifiers and next evidence boundary

- Current conditional Shadow gate FAILS: too few shape cases, source/date composition shifts, no linear holdout entry, severe density/endpoint censoring and no as-of vault overlap.
- Regularity-only scam interpretation is contradicted by observed staircase right tails; it must never become a hard veto or funded alpha by itself.
- A later proposal needs independent prospective dense same-pool coverage, authenticated contemporaneous manipulation evidence, persistent hazard enrichment across time/source/chain, and explicit tail/positive-first sacrifice accounting. If the apparent benefit disappears after source or coverage matching, or removes most right tails, reject it.
- No threshold search, all-old-token watch expansion, history backfill or hindsight labeling to repair insufficient supply. This boundary completes the requested bounded validation; future runtime Shadow requires new supporting evidence.

Artifacts: `data/research/path_shape101/{rows,result}.json`; reproducible script `scripts/research_path_shape101.py`; tests `tests/test_research_path_shape101.py`. Raw artifacts remain local/ignored, not runtime state.
