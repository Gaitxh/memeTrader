# Conditional runner66 — frozen21 as-of comparison

REPLY_TO: C2C-20260909-S1-CONDITIONAL-RUNNER-66
Disposition: REJECT_NO_REGISTRATION

Predeclared qualitative state protocol CONDITIONAL_RUNNER_PREREG_66.md preceded calculations. Reused exactly58's21 clean terminal treatment-exposed pairs at frozen04:09:42Z cutoff, not newer outcomes. Each cutoff verified against actual fast TIME_EXIT mark recorded_at and against no predecision partial SELL. Decisions0.118–1.949s after nominal900s; next SELL fill not used as feature. Entry exact pool, token-indexed snapshots with observed<=ingested<=recorded<=decision, record lag<=15s, price>0/liquidity>=1000. All21 have retained quote within30s. Quantity includes buy4%; hypothetical full liquidation at price*.96 minus actual5U stake, no extra fee. Retained snapshots are not every held tick; high/retention are sampled lower-bound extrema, not final position high (which was never read as a feature). Postconfirmation SELL quote is excluded. Mark history is10s sampled/6h retained, so cannot recover all exact runtime peaks. Full available buy/sell5m and volume aggregates retained, not actual directional money flow or wallets.

Incremental outcome=runner minus fast (positive means holding helped):

|Predecision state|N|incremental U|median U|beneficial|
|---|---:|---:|---:|---:|
|Economic positive|11|-64.469237|-0.865729|1|
|Underwater/nonpositive|10|+4.866356|+0.214071|7|
|Liquidity below entry|5|-0.058695|-0.216818|2|
|Liquidity >=entry|16|-59.544185|-0.556138|6|
|Price down vs60s prior|4|-30.604279|-0.769312|0|
|Price not down|17|-28.998601|-0.216818|8|
|5m volume cooling vs300s prior|8|-3.466878|-0.075405|4|
|Not cooling|13|-56.136002|-0.844023|4|

Frozen conjunction positive + liquidity>=entry + nonnegative60s direction + volume not cooling:6 pairs,delta-27.053103U,median-1.372973,1/6 beneficial. Remove greatest beneficial1 =>-39.131066; remove top3=>-37.406065. Chains BSC1 -28.639243,SOL3 +3.311140,RH2 -1.725001; dates Sep8 -37.250848/Sep9 +10.197744. Not stable across chain/date. Underwater group's apparent benefit also fails top3 removal(-0.575770); do not invert rule post hoc.

Decisive counterexample9a50...:15m economic+472.785%,liquidity2.484x entry,1.0 sampled liquidity-high retention,0 sampled price drawdown,noncooling volume/nonnegative direction; later floor-writeoff yields-28.639243U incremental. Other floor-writeoff5138...:+480.876%,2.514x entry,0.9467 liquidity-high retention,price drawdown-10.472%,direction down; incremental-29.043815U. Thus one visible weakening case but another looks fully supported. These are descriptive examples, never token selectors.

All21 states have usable retained comparisons; future missing would remain UNKNOWN. No nearby thresholds or optimization. Small selected sample, source sampling and tail concentration prevent a causal/robust generalization. Simple proposed monotone support rule is rejected; no Paper pair, no parameter/account/runtime/funding/history changes, no reset/backfill/Live. Existing S1 stays unchanged. Exact predictive success would require prospective independent observations; this task provides a falsification, not another strategy.

Validation: script assertions verify frozen21 membership, actual decision timestamps and no previous partial exit; rows preserve snapshot IDs/clocks/source, sampled high and liquidity retention. Report data/research/conditional66/result.json; script scripts/research_conditional66.py. No runtime deployment/tests necessary. Later outcome pairing uses already frozen58 ledger; no revised PnL.
