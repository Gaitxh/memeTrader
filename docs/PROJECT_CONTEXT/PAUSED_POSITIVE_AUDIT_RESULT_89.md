# Paused-positive audit89 — corrected lifecycle, no mechanical reopening

REPLY_TO: C2C-20260909-PAUSED-POSITIVE-AUDIT-89

Frozen current-period cutoff 2026-09-09T08:17:24.116958Z: 255 policies, 241 paused, 39,668 position rows. A single read-only snapshot took0.992s. No current-period contamination/void entries found. All241 paused/retired arms are enumerated below; ACTIVE14 remain unchanged. This is not an audit of obsolete funding periods. No manual reopening, funding change, history rewrite, backfill or Live activation.

## Findings that challenge prior labels

There are9 positive paused arms. None should be described as economic failure merely because paused. The old UI used generic operational pause/retirement labels, not a universal FAILED label; some prior mixed reasons nevertheless conflated failed treatment with profitable control. Added a separate evidence assessment while preserving operational pause state. FAILED here means stopped negative observed experiment, not proof of negative population alpha; samples<30, zero-input/rule sparse and orphan closure are conservatively separated.

254-V001 age_rate_horizon_fast_v1 is EXPERIMENT_COMPLETE_POSITIVE:33 terminals,+101.7183148985U, PF9.091574, expectancy+3.082373U, median-.303611U, trimmed10% mean+1.125007U, top3-profit removal still+25.542810U. No catastrophic(<=-50% stake) terminal. It is a genuinely positive observed defensive variant, not FAILED and not a redundant exit hash.

Independent exact common-fill match: all33 share nonempty source_entry_fill_id/token plus identical source_buy_trade_id, entry_snapshot_id, stake, execution price, quantity and opened_at with parent resource_age_rate_candidate_v1. Fast+101.718315 vs parent+323.319884; delta-221.601569U. Fast wins/ties/loss15/5/13. Remove three largest positive fast-parent deltas: -230.467674U. Conservative storm-overlap exclusion leaves31, delta-221.614341U (different from earlier cutoff77; no forced reconciliation of unequal cohorts). Row pointers preserved in result.json. Positive-arm/reference trade ledger663 rows reconciles to position realized PnL with0 errors at frozen trade frontier.

Defensive tradeoff is real: common33 fast loss dollars12.570893 vs parent18.562529, saving5.991636; sacrifices227.593205 positive-profit dollars. Worst fast-2.111830 vs parent-4.998269; catastrophe0 vs1; median fast slightly worse(-.303611 vs-.287163). Thus parent is not superior on every downside metric, but fast has not justified duplicate funded enrollment or replacing it under the current net-profit objective. Keep formal two-arm S1 pause (paired size2), retain254 as a defensive research/Shadow benchmark for future direct-parent comparisons. No new Shadow process, continuous counterfactual ledger or resumed buys are claimed: future benchmark evaluation requires causal later observations and its own coverage accounting. Faster capital release is plausible but not measured here as portfolio improvement.

160-V002 market_regime_throttle_v1:9,+19.622548U. Common6 with event_reawakening exact fills/PnL=+30.232491 each, delta0; extra3 all losses,-10.609943. Classify DUPLICATE_SUPERSEDED as empirical dominated superset, NOT identical policy or economic failure. N9 remains small; this is capital consolidation, not universal rejection.

250-V001 early_impulse_profit_lock_control_v1:47,+18.562584U. All47 exact same fills and PnL as early_impulse_trailing_60m_v1; identical behavior hash a6d849c623f920b6. Positive at its shorter historical enrollment frontier; original trailing's larger sample later deteriorated. Classify DUPLICATE_SUPERSEDED with positive completed control evidence, not failed control. Top1 removed=-36.229516U, top3=-57.520726U. Do not reopen old failed treatment or create another60m copy.

Other6 positive retired duplicates: strategies027/031/059/079/109/124 each2 terminals,+1.899417U. Exact2 common fills/PnL equal their recorded representative, shared hash7c8fb78641cf1625. Top1 removed=-2.126282U; no independent risk-adjusted advantage. Representatives may themselves later have paused; this does not turn the historical copies into new independent evidence.

Across all241 stopped arms, no additional negative-total arm has positive median or positive trimmed10% mean in this frozen sample. No overlooked independent positive arm beyond254 was found. This scan cannot prove all pause decisions optimal in unobserved future regimes. Low-N negative arms now receive INSUFFICIENT rather than FAILED; input-blocked arms receive DATA_BLOCKED; paired orphan resource_profit_structure_control receives INSUFFICIENT. Underlying collectors and contracts preserved.

## Actual correction

Add display-only assessment_status/note/evidence to existing version-scoped control records; the state/representative/reason and all enrollment fields remain identical. Store forwards metadata, compact API/universe exposes it, UI distinguishes six assessment classes while retaining pause/exit text. Existing retired filtering unchanged. Seven-table funding/registration hash before/after b376b3e07f9f4aae836dec63a5d54a95641eca89cd221cdfd142a355ef12a2fd. Only Web service reload is needed; trading runtime untouched. No new account/strategy/shadow worker.

Validation: targeted web lifecycle/cache test PASS; JS six labels plus legacy labels/positive-paused label PASS. Runtime-control mutation transaction asserts display-only differences and immutable registration/funding. Statistical script uses no fitted thresholds;30-terminal partition is a conservative evidence-label boundary, never a trading gate. Classification is as-of, not automatically recalculated to reactivate accounts.

Deployment acceptance: Web-only launcher reloaded; first cold API sequence timed out and was not reported as PASS. Subsequent bounded health/live/universe requests succeeded. Live API independently exposes160/250 as DUPLICATE_SUPERSEDED and254 as EXPERIMENT_COMPLETE_POSITIVE; universe confirms display_index254, assessment EXPERIMENT_COMPLETE_POSITIVE, account_lifecycle PAUSED_NEW_ENTRY, forward_enabled=false. Static label behavior is covered by the Node test; no browser screenshot/visual inspection is claimed. Evidence accept_health.json,accept_api_live.json,accept_universe.json. Trading runtime was not restarted.

## Complete current policy disposition

Counts: {"FAILED": 163, "DUPLICATE_SUPERSEDED": 61, "ACTIVE": 14, "INSUFFICIENT": 12, "DATA_BLOCKED": 4, "EXPERIMENT_COMPLETE_POSITIVE": 1}

|Arm|Assessment|Terminals|Net U|Median U|Top3 removed U|Existing pause basis|
|---|---|---:|---:|---:|---:|---|
|canonical-0006b989b189e0ac|FAILED|191|-984.5390|-2.9921|-1091.0097|user_requested_retirement_equity_below_50_of_1000|
|canonical-0186f1e75b238e63|FAILED|58|-359.5255|-7.3580|-413.4661|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|canonical-0356dc612c90a689|DUPLICATE_SUPERSEDED|191|-984.5390|-2.9921|-1091.0097|same contract and identical common trade paths; preserve representative/history|
|canonical-035ad2cf0cb0f6a5|FAILED|181|-982.3111|-1.8539|-1088.2965|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|canonical-05005fdaa932d3d0|FAILED|137|-989.5748|-18.7145|-1574.6865|user_requested_retirement_equity_below_50_of_1000|
|canonical-058b868fbd1d8065|DUPLICATE_SUPERSEDED|2|-8.8482|-4.4241|UNKNOWN|same contract and identical common trade paths; preserve representative/history|
|canonical-0ad93cd8a7bec9ec|FAILED|133|-877.9388|-8.9109|-1143.5670|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|canonical-0c198e6aa30fa049|FAILED|137|-860.7004|-8.8259|-1091.3782|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|canonical-0cd0f3c790d85ca5|FAILED|110|-984.6628|-17.8379|-1277.2294|user_requested_retirement_equity_below_50_of_1000|
|canonical-0d7caccf76779d74|FAILED|157|-984.7423|-17.3411|-1524.0660|user_requested_retirement_equity_below_50_of_1000|
|canonical-0df3639e1824ad0f|FAILED|162|-992.8861|-2.5161|-1110.0817|user_requested_retirement_equity_below_50_of_1000|
|dex-successor-012-0eea3c62cb7bacc4|FAILED|166|-980.8630|-2.6426|-1080.1171|user_requested_retirement_equity_below_50_of_1000|
|canonical-10af25fd9780e2af|FAILED|133|-877.9388|-8.9109|-1143.5670|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|dex-successor-014-1375c87c13cb1de1|FAILED|58|-374.5549|-7.4094|-423.1846|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|canonical-18d8ce34c0112abb|FAILED|58|-194.8979|-1.9447|-226.9625|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|canonical-195049e27d177b1f|FAILED|124|-994.6264|-19.3047|-1521.0502|user_requested_retirement_equity_below_50_of_1000|
|canonical-19b9d4d442fde1ab|DUPLICATE_SUPERSEDED|191|-984.5390|-2.9921|-1091.0097|same contract and identical common trade paths; preserve representative/history|
|canonical-1c2ac45bb5154011|DUPLICATE_SUPERSEDED|191|-984.5390|-2.9921|-1091.0097|same contract and identical common trade paths; preserve representative/history|
|dex-successor-019-1d5937dec4e156d4|FAILED|58|-374.5549|-7.4094|-423.1846|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|canonical-1d9647200c714796|FAILED|181|-982.3111|-1.8539|-1088.2965|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|canonical-1ef2715c090f60fb|DUPLICATE_SUPERSEDED|167|-880.7513|-1.7899|-986.7367|same contract and identical common trade paths; preserve representative/history|
|canonical-22dbe223b3814f7f|FAILED|162|-992.8861|-2.5161|-1110.0817|user_requested_retirement_equity_below_50_of_1000|
|canonical-2390fb342a6e90b6|FAILED|146|-981.7737|-8.0171|-1142.9806|user_requested_retirement_equity_below_50_of_1000|
|canonical-24ac3d4a360ab98c|DUPLICATE_SUPERSEDED|167|-880.7513|-1.7899|-986.7367|same contract and identical common trade paths; preserve representative/history|
|dex-successor-025-2509c2f13f40a238|FAILED|132|-889.4637|-9.0910|-1155.0919|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|dex-successor-026-25ad46e118f6edc9|FAILED|146|-983.9762|-4.2294|-1105.1438|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|canonical-25cfdc3e9adf23df|DUPLICATE_SUPERSEDED|2|1.8994|0.9497|UNKNOWN|same contract and identical common trade paths; preserve representative/history|
|canonical-2634d7c52e35b317|FAILED|58|-374.5549|-7.4094|-423.1846|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|canonical-2d3874b5b4dfe162|DUPLICATE_SUPERSEDED|162|-992.8861|-2.5161|-1110.0817|same contract and identical common trade paths; preserve representative/history|
|canonical-3028ef000f6df93d|FAILED|58|-359.5255|-7.3580|-413.4661|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|canonical-3093112db36e72a6|DUPLICATE_SUPERSEDED|2|1.8994|0.9497|UNKNOWN|same contract and identical common trade paths; preserve representative/history|
|dex-successor-032-30d85f39d76f4f18|FAILED|166|-980.8630|-2.6426|-1080.1171|user_requested_retirement_equity_below_50_of_1000|
|canonical-3733dc40ac3c74ea|FAILED|137|-860.7004|-8.8259|-1091.3782|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|canonical-39063fa299ee2cfd|FAILED|137|-860.7004|-8.8259|-1091.3782|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|dex-successor-035-3be68fb41c7f0536|DUPLICATE_SUPERSEDED|11|-24.4885|-3.3773|-61.7037|same contract and identical common trade paths; preserve representative/history|
|canonical-3c89090af7e8cd6b|DUPLICATE_SUPERSEDED|2|-8.8482|-4.4241|UNKNOWN|same contract and identical common trade paths; preserve representative/history|
|canonical-427d6a31e0a2e604|DUPLICATE_SUPERSEDED|2|-8.8482|-4.4241|UNKNOWN|same contract and identical common trade paths; preserve representative/history|
|dex-successor-038-45d45a6774225417|DUPLICATE_SUPERSEDED|2|-8.8482|-4.4241|UNKNOWN|same contract and identical common trade paths; preserve representative/history|
|dex-successor-039-46f730df93b191f3|FAILED|166|-980.8630|-2.6426|-1080.1171|user_requested_retirement_equity_below_50_of_1000|
|canonical-4a27a58cc5902ea9|FAILED|182|-984.7470|-9.2746|-1322.5044|user_requested_retirement_equity_below_50_of_1000|
|dex-successor-041-4a4be8bd60c050f5|FAILED|146|-983.9762|-4.2294|-1105.1438|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|canonical-4b290f4f2bba4fb4|FAILED|191|-984.5390|-2.9921|-1091.0097|user_requested_retirement_equity_below_50_of_1000|
|canonical-504d9582ca75a709|DUPLICATE_SUPERSEDED|2|-8.8482|-4.4241|UNKNOWN|same contract and identical common trade paths; preserve representative/history|
|canonical-5054a25aae97fdf9|FAILED|158|-661.2292|-3.9080|-728.4367|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|canonical-53316326d5f1f7d5|DUPLICATE_SUPERSEDED|167|-880.7513|-1.7899|-986.7367|same contract and identical common trade paths; preserve representative/history|
|dex-successor-046-546560b93b10c79c|FAILED|240|-986.5518|-1.7687|-1223.4043|user_requested_retirement_equity_below_50_of_1000|
|canonical-57d44c510448173c|DUPLICATE_SUPERSEDED|167|-880.7513|-1.7899|-986.7367|same contract and identical common trade paths; preserve representative/history|
|canonical-5a16583de92bac39|DUPLICATE_SUPERSEDED|2|-8.8482|-4.4241|UNKNOWN|same contract and identical common trade paths; preserve representative/history|
|dex-successor-049-5ce40de1d93304fb|FAILED|174|-987.3097|-2.6900|-1175.0099|user_requested_retirement_equity_below_50_of_1000|
|canonical-619d142075228d0e|FAILED|58|-374.5549|-7.4094|-423.1846|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|canonical-627c3b1e3fc4157d|FAILED|158|-661.2292|-3.9080|-728.4367|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|dex-successor-052-62d73d37cb094974|DUPLICATE_SUPERSEDED|166|-980.8630|-2.6426|-1080.1171|same contract and identical common trade paths; preserve representative/history|
|canonical-63e62a12e74b6320|FAILED|148|-980.4872|-8.3618|-1045.5096|user_requested_retirement_equity_below_50_of_1000|
|canonical-6423ca6248abf0f9|FAILED|137|-860.7004|-8.8259|-1091.3782|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|canonical-65e78965552bd91b|FAILED|133|-877.9388|-8.9109|-1143.5670|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|canonical-69be52c97c1c686d|FAILED|158|-661.2292|-3.9080|-728.4367|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|canonical-6c728fb1b79d226a|DUPLICATE_SUPERSEDED|191|-984.5390|-2.9921|-1091.0097|same contract and identical common trade paths; preserve representative/history|
|dex-successor-058-6e2af57081e33ce0|DUPLICATE_SUPERSEDED|11|-24.4885|-3.3773|-61.7037|same contract and identical common trade paths; preserve representative/history|
|canonical-707c4491ca3caf89|DUPLICATE_SUPERSEDED|2|1.8994|0.9497|UNKNOWN|same contract and identical common trade paths; preserve representative/history|
|canonical-744153cee3d16c08|DUPLICATE_SUPERSEDED|162|-992.8861|-2.5161|-1110.0817|same contract and identical common trade paths; preserve representative/history|
|canonical-75dadf52fc0cdd9e|FAILED|96|-982.1025|-11.6263|-1098.2682|user_requested_retirement_equity_below_50_of_1000|
|dex-successor-062-7726580fd0f701f1|DUPLICATE_SUPERSEDED|11|-24.4885|-3.3773|-61.7037|same contract and identical common trade paths; preserve representative/history|
|canonical-7c7c863ffc06fdf6|FAILED|128|-981.2578|-18.1573|-1507.6815|user_requested_retirement_equity_below_50_of_1000|
|canonical-7c86e5fc9e55178e|FAILED|158|-661.2292|-3.9080|-728.4367|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|canonical-831b37e3aaeaa64d|FAILED|186|-996.7594|-7.1812|-1077.2137|user_requested_retirement_equity_below_50_of_1000|
|canonical-83fdc6be4ed5e6bf|DUPLICATE_SUPERSEDED|162|-992.8861|-2.5161|-1110.0817|same contract and identical common trade paths; preserve representative/history|
|dex-successor-067-842383c9376853b7|FAILED|166|-980.8630|-2.6426|-1080.1171|user_requested_retirement_equity_below_50_of_1000|
|dex-successor-068-85b7ea76ae522727|FAILED|166|-980.8630|-2.6426|-1080.1171|user_requested_retirement_equity_below_50_of_1000|
|dex-successor-069-88446f2e2831bb0d|FAILED|132|-889.4637|-9.0910|-1155.0919|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|dex-successor-070-8a6c18233b0c33fd|DUPLICATE_SUPERSEDED|2|-8.8482|-4.4241|UNKNOWN|same contract and identical common trade paths; preserve representative/history|
|canonical-8e0e2a5367a26beb|DUPLICATE_SUPERSEDED|167|-880.7513|-1.7899|-986.7367|same contract and identical common trade paths; preserve representative/history|
|canonical-8eed440ae6e40cdf|FAILED|137|-860.7004|-8.8259|-1091.3782|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|canonical-91e44b09867ae22e|FAILED|133|-877.9388|-8.9109|-1143.5670|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|dex-successor-074-94e2a27a7c53d44c|DUPLICATE_SUPERSEDED|2|-8.8482|-4.4241|UNKNOWN|same contract and identical common trade paths; preserve representative/history|
|dex-successor-075-977f322fba28b9bc|DUPLICATE_SUPERSEDED|166|-980.8630|-2.6426|-1080.1171|same contract and identical common trade paths; preserve representative/history|
|canonical-9b8c8540532b6db2|FAILED|158|-661.2292|-3.9080|-728.4367|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|canonical-9e8b8ab496229059|DUPLICATE_SUPERSEDED|2|-8.8482|-4.4241|UNKNOWN|same contract and identical common trade paths; preserve representative/history|
|dex-successor-078-9eab102528bb48c4|DUPLICATE_SUPERSEDED|11|-24.4885|-3.3773|-61.7037|same contract and identical common trade paths; preserve representative/history|
|canonical-9fdcf1c1c121b928|DUPLICATE_SUPERSEDED|2|1.8994|0.9497|UNKNOWN|same contract and identical common trade paths; preserve representative/history|
|canonical-a0b46b71b30d8575|FAILED|182|-984.7470|-9.2746|-1322.5044|user_requested_retirement_equity_below_50_of_1000|
|canonical-a6741f19300d52f1|DUPLICATE_SUPERSEDED|191|-984.5390|-2.9921|-1091.0097|same contract and identical common trade paths; preserve representative/history|
|canonical-a7ca496301c23662|FAILED|133|-877.9388|-8.9109|-1143.5670|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|canonical-aa3ecee6b712fc53|FAILED|137|-860.7004|-8.8259|-1091.3782|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|canonical-aa5d0c9d6721fb48|FAILED|180|-981.5279|-17.4189|-1850.7279|user_requested_retirement_equity_below_50_of_1000|
|canonical-ac6059d9867697cd|DUPLICATE_SUPERSEDED|2|-8.8482|-4.4241|UNKNOWN|same contract and identical common trade paths; preserve representative/history|
|canonical-adc90ff111d03016|FAILED|158|-661.2292|-3.9080|-728.4367|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|canonical-addb9efa1916afbf|DUPLICATE_SUPERSEDED|2|-8.8482|-4.4241|UNKNOWN|same contract and identical common trade paths; preserve representative/history|
|dex-successor-088-b18c9c129af7fbfc|DUPLICATE_SUPERSEDED|166|-980.8630|-2.6426|-1080.1171|same contract and identical common trade paths; preserve representative/history|
|canonical-b1c6865d30e91ddd|FAILED|58|-194.8979|-1.9447|-226.9625|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|dex-successor-090-b5ad5642ccff0e2e|DUPLICATE_SUPERSEDED|142|-974.0575|-4.2731|-1095.2251|same contract and identical common trade paths; preserve representative/history|
|canonical-bcf4041ab4578717|DUPLICATE_SUPERSEDED|2|-8.8482|-4.4241|UNKNOWN|same contract and identical common trade paths; preserve representative/history|
|dex-successor-092-bd048c8b412c53b5|DUPLICATE_SUPERSEDED|11|-24.4885|-3.3773|-61.7037|same contract and identical common trade paths; preserve representative/history|
|canonical-c2f29f5b78e5a3a9|FAILED|137|-860.7004|-8.8259|-1091.3782|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|dex-successor-094-c39421bc0ad61a44|DUPLICATE_SUPERSEDED|142|-974.0575|-4.2731|-1095.2251|same contract and identical common trade paths; preserve representative/history|
|dex-successor-095-c78ed4ffa4877807|FAILED|166|-980.8630|-2.6426|-1080.1171|user_requested_retirement_equity_below_50_of_1000|
|canonical-c9204a1e7a1c45f3|DUPLICATE_SUPERSEDED|167|-880.7513|-1.7899|-986.7367|same contract and identical common trade paths; preserve representative/history|
|canonical-ca8f32cf0d565e07|FAILED|264|-946.4452|-8.6083|-1529.5180|user_requested_retirement_equity_below_50_of_1000|
|canonical-cae3a114676b9324|DUPLICATE_SUPERSEDED|191|-984.5390|-2.9921|-1091.0097|same contract and identical common trade paths; preserve representative/history|
|dex-successor-099-cb5e6c13704cb97a|DUPLICATE_SUPERSEDED|11|-24.4885|-3.3773|-61.7037|same contract and identical common trade paths; preserve representative/history|
|canonical-cca8c50b00503869|DUPLICATE_SUPERSEDED|2|-8.8482|-4.4241|UNKNOWN|same contract and identical common trade paths; preserve representative/history|
|dex-successor-101-d1cb0c9edad31cbf|DUPLICATE_SUPERSEDED|142|-974.0575|-4.2731|-1095.2251|same contract and identical common trade paths; preserve representative/history|
|canonical-d276043eb5aa27c2|DUPLICATE_SUPERSEDED|162|-992.8861|-2.5161|-1110.0817|same contract and identical common trade paths; preserve representative/history|
|canonical-d69a266410f4ef7a|FAILED|133|-877.9388|-8.9109|-1143.5670|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|canonical-d785aa5181f97422|DUPLICATE_SUPERSEDED|162|-992.8861|-2.5161|-1110.0817|same contract and identical common trade paths; preserve representative/history|
|canonical-db22c376fcd22466|FAILED|137|-860.7004|-8.8259|-1091.3782|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|dex-successor-106-db27127f672cbae7|DUPLICATE_SUPERSEDED|2|-8.8482|-4.4241|UNKNOWN|same contract and identical common trade paths; preserve representative/history|
|canonical-ddd57b024d84a00b|FAILED|124|-996.2577|-19.3236|-1522.6815|user_requested_retirement_equity_below_50_of_1000|
|dex-successor-108-e44a1533954c80e5|DUPLICATE_SUPERSEDED|142|-974.0575|-4.2731|-1095.2251|same contract and identical common trade paths; preserve representative/history|
|canonical-e7b74ce032fcc5d3|DUPLICATE_SUPERSEDED|2|1.8994|0.9497|UNKNOWN|same contract and identical common trade paths; preserve representative/history|
|canonical-e87e33896472940a|FAILED|133|-877.9388|-8.9109|-1143.5670|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|canonical-e8ad7db7c6a6386c|FAILED|158|-661.2292|-3.9080|-728.4367|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|dex-successor-112-ea5a51ca3135e1b8|DUPLICATE_SUPERSEDED|142|-974.0575|-4.2731|-1095.2251|same contract and identical common trade paths; preserve representative/history|
|canonical-eaaf188e7835376f|DUPLICATE_SUPERSEDED|162|-992.8861|-2.5161|-1110.0817|same contract and identical common trade paths; preserve representative/history|
|canonical-eb1795742aed4576|FAILED|133|-877.9388|-8.9109|-1143.5670|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|canonical-ecc266d212b9d0ef|FAILED|158|-661.2292|-3.9080|-728.4367|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|canonical-ef7bf4f71eeacb75|DUPLICATE_SUPERSEDED|2|-8.8482|-4.4241|UNKNOWN|same contract and identical common trade paths; preserve representative/history|
|canonical-efdc816cff3321dd|DUPLICATE_SUPERSEDED|2|-8.8482|-4.4241|UNKNOWN|same contract and identical common trade paths; preserve representative/history|
|dex-successor-118-f336bf0ae10004cd|DUPLICATE_SUPERSEDED|166|-980.8630|-2.6426|-1080.1171|same contract and identical common trade paths; preserve representative/history|
|dex-successor-119-f3cf5416894220d7|DUPLICATE_SUPERSEDED|166|-980.8630|-2.6426|-1080.1171|same contract and identical common trade paths; preserve representative/history|
|dex-successor-120-f98e117baa206954|FAILED|97|-983.5567|-11.4969|-1050.4668|user_requested_retirement_equity_below_50_of_1000|
|dex-successor-121-fa93589262a321f9|DUPLICATE_SUPERSEDED|2|-8.8482|-4.4241|UNKNOWN|same contract and identical common trade paths; preserve representative/history|
|dex-successor-122-fa9e8436a3a39c63|DUPLICATE_SUPERSEDED|2|-8.8482|-4.4241|UNKNOWN|same contract and identical common trade paths; preserve representative/history|
|dex-successor-123-fdcf73ca24c18fcc|DUPLICATE_SUPERSEDED|142|-974.0575|-4.2731|-1095.2251|same contract and identical common trade paths; preserve representative/history|
|canonical-fddc0b4e14f1836f|DUPLICATE_SUPERSEDED|2|1.8994|0.9497|UNKNOWN|same contract and identical common trade paths; preserve representative/history|
|broad_principal_lock_runner_v1|FAILED|210|-997.1253|-2.2169|-1283.8479|user_requested_retirement_equity_below_50_of_1000|
|broad_flash_tail_first_mover_v1|FAILED|146|-990.2310|-7.3218|-1073.1525|user_requested_retirement_equity_below_50_of_1000|
|broad_mature_continuity_control_v1|FAILED|175|-985.3347|-4.1926|-1060.2314|user_requested_retirement_equity_below_50_of_1000|
|broad_cost_coverage_scaleout_v1|FAILED|204|-982.4277|-1.7711|-1082.7060|user_requested_retirement_equity_below_50_of_1000|
|experiment_quiet_reawakening_candidate_v1|ACTIVE|1|-4.1631|-4.1631|UNKNOWN|Active|
|experiment_quiet_reawakening_control_v1|FAILED|98|-97.1912|-1.5388|-145.0570|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|experiment_sustained_breakout_candidate_v1|FAILED|188|-995.3225|-4.6146|-1061.4116|user_requested_retirement_equity_below_50_of_1000|
|experiment_sustained_breakout_control_v1|FAILED|188|-984.2190|-4.7180|-1052.5368|user_requested_retirement_equity_below_50_of_1000|
|experiment_pullback_reclaim_candidate_v1|FAILED|236|-230.7063|-4.3208|-309.0653|convergence54: material realized loss with >=30 unique terminal tokens; depleted or failed evidence; preserve exits/history; no replacement|
|experiment_pullback_reclaim_control_v1|FAILED|209|-982.6355|-4.5159|-1056.7643|user_requested_retirement_equity_below_50_of_1000|
|experiment_conditional_runner_candidate_v1|FAILED|342|-981.3596|-1.5385|-1037.8809|user_requested_retirement_equity_below_50_of_1000|
|experiment_conditional_runner_control_v1|FAILED|342|-760.1298|-1.0566|-816.6511|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|experiment_panic_reclaim_candidate_v1|FAILED|285|-712.7385|-4.3379|-794.9509|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|experiment_panic_reclaim_control_v1|FAILED|348|-647.4871|-4.3718|-729.6996|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|experiment_support_risk_candidate_v1|FAILED|183|-432.9211|-1.2441|-473.9685|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|experiment_support_risk_control_v1|FAILED|183|-457.7996|-1.2441|-498.8471|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|experiment_migration_candidate_v1|FAILED|331|-820.7650|-1.3126|-880.1611|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|experiment_migration_control_v1|FAILED|350|-887.6493|-1.3618|-944.3229|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|experiment_participation_candidate_v1|FAILED|297|-998.0063|-3.1859|-1084.9158|user_requested_retirement_equity_below_50_of_1000|
|experiment_participation_control_v1|FAILED|45|-71.7069|-1.5125|-78.0242|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|experiment_narrative_candidate_v1|FAILED|292|-982.4898|-4.0600|-1056.4888|user_requested_retirement_equity_below_50_of_1000|
|experiment_narrative_control_v1|FAILED|273|-990.4682|-4.2368|-1076.1231|user_requested_retirement_equity_below_50_of_1000|
|vault_hazard_v1|FAILED|251|-699.6980|-1.3618|-755.3421|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|earn_the_hold_v1|FAILED|30|-56.4971|-1.5561|-53.5356|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|failed_continuation_profit_lock_v1|FAILED|30|-284.3360|-11.5094|-324.5076|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|wave_reset_reentry_v1|FAILED|67|-95.9188|-1.5231|-101.0089|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|migration_absorption_v1|INSUFFICIENT|17|-22.6193|-1.5385|-32.0011|convergence74: reviewed negative economics or completed S1 same-fill horizon comparison; close whole mandatory pair without replacement; preserve shared collectors/parent/history/exits|
|executable_recovery_decay_v1|FAILED|251|-704.5040|-1.3548|-760.1481|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|capital_velocity_v1|FAILED|159|-491.8300|-1.5385|-579.2160|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|effective_breadth_v1|INSUFFICIENT|11|-46.8451|-1.5229|-46.9196|convergence70: small-sample negative distribution; no compensating tail; user-directed convergence; preserve shared collectors/parent/history/exits|
|price_to_flow_fragility_v1|FAILED|30|-55.1169|-1.4871|-52.2215|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|churn_resistant_v1|FAILED|68|-137.1973|-1.5020|-136.3122|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|creator_early_holder_distribution_v1|FAILED|32|-58.0586|-1.4973|-55.1865|convergence54: material realized loss with >=30 unique terminal tokens; depleted or failed evidence; preserve exits/history; no replacement|
|bundle_adjusted_breadth_v1|FAILED|55|-104.1407|-1.4866|-122.9769|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|finite_capital_ranker_v1|FAILED|177|-981.3450|-4.8624|-1127.8723|user_requested_retirement_equity_below_50_of_1000|
|market_regime_throttle_v1|DUPLICATE_SUPERSEDED|9|19.6225|-4.0428|-26.8433|convergence61: empirical common6 same-fill delta0; extra3 all losses; preserve exits/history; no policy identity claim|
|competing_risk_v1|INSUFFICIENT|0|0.0000|UNKNOWN|UNKNOWN|convergence64: RULE_SPARSE; zero full-period positions/decisions; no recent ready; explicit input repair/new forward version required; no threshold relaxation|
|high_recall_exit_pipeline_v1|FAILED|93|-196.3604|-1.5599|-193.8508|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|direct_lp_float_constrained_v1|INSUFFICIENT|10|-24.6577|-2.1895|-24.2051|convergence70: small-sample negative distribution; no compensating tail; user-directed convergence; preserve shared collectors/parent/history/exits|
|authoritative_event_shock_v1|FAILED|185|-988.3782|-4.9892|-1146.3218|user_requested_retirement_equity_below_50_of_1000|
|serial_conditional_runner_v1|FAILED|305|-981.5859|-1.5385|-1021.2904|convergence54: material realized loss with >=30 unique terminal tokens; depleted or failed evidence; preserve exits/history; no replacement|
|sustained_breakout_earn_hold_v1|FAILED|101|-219.3748|-3.4082|-269.6575|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|event_reawakening_v1|ACTIVE|6|30.2325|-3.5330|-16.0654|Active|
|surface_lifecycle_pipeline_v1|ACTIVE|3|-5.0761|-0.4571|0.0000|Active|
|paired_vault_hazard_candidate_v1|FAILED|251|-694.3402|-1.3555|-749.9843|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|paired_vault_hazard_control_v1|FAILED|251|-695.8425|-1.3548|-751.4866|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|paired_earn_the_hold_candidate_v1|FAILED|30|-56.4971|-1.5561|-53.5356|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|paired_earn_the_hold_control_v1|FAILED|30|-55.1169|-1.4871|-52.2215|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|paired_failed_continuation_profit_lock_candidate_v1|FAILED|30|-284.3360|-11.5094|-324.5076|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|paired_failed_continuation_profit_lock_control_v1|FAILED|30|-284.3360|-11.5094|-324.5076|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|prebreakout_net_accumulation_v1|ACTIVE|97|3.9811|-0.4904|-33.8911|Active|
|liquidity_leads_price_v1|ACTIVE|2|-6.5671|-3.2836|UNKNOWN|Active|
|fast_stop_reclaim_v1|FAILED|335|-323.2806|-1.1685|-371.5899|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|no_ca_event_flow_leader_v1|FAILED|137|-72.9655|-1.0039|-96.0360|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|duration_competing_risk_v1|INSUFFICIENT|0|0.0000|UNKNOWN|UNKNOWN|convergence64: RULE_SPARSE; zero full-period positions/decisions; no recent ready; explicit input repair/new forward version required; no threshold relaxation|
|direct_lp_amount_specific_confirmed_v1|FAILED|775|-631.8026|-0.7665|-680.5288|convergence42: explicit deep-loss subset, >=100 terminal tokens/loss>=200U/recent enrollment/no pairing or contamination records; prior mean -1U filter intentionally superseded for named subset|
|official_event_actual_flow_v1|FAILED|657|-501.9162|-1.0978|-580.7697|convergence42: explicit deep-loss subset, >=100 terminal tokens/loss>=200U/recent enrollment/no pairing or contamination records; prior mean -1U filter intentionally superseded for named subset|
|migration_amount_rate_absorption_v1|FAILED|558|-518.8883|-1.1240|-586.9250|convergence42: explicit deep-loss subset, >=100 terminal tokens/loss>=200U/recent enrollment/no pairing or contamination records; prior mean -1U filter intentionally superseded for named subset|
|early_observed_buyer_distribution_v1|FAILED|31|-13.9990|-0.3698|-13.2809|convergence67: >=30 terminals and zero winners; negative costs-after evidence; preserve shared collectors/parent/history/exits|
|common_funding_adjusted_breadth_5u_v1|FAILED|938|-999.1220|-1.0767|-1074.1118|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|observed_cycle_reset_reacceleration_v1|INSUFFICIENT|0|0.0000|UNKNOWN|UNKNOWN|convergence64: RULE_SPARSE; zero full-period positions/decisions; no recent ready; explicit input repair/new forward version required; no threshold relaxation|
|observed_cycle_reset_reacceleration_control_v1|FAILED|61|-17.3641|-0.4665|-22.8082|convergence74: reviewed negative economics or completed S1 same-fill horizon comparison; close whole mandatory pair without replacement; preserve shared collectors/parent/history/exits|
|volatility_scaled_depth_flow_momentum_v1|FAILED|364|-311.1130|-1.0775|-325.8733|convergence42: explicit deep-loss subset, >=100 terminal tokens/loss>=200U/recent enrollment/no pairing or contamination records; prior mean -1U filter intentionally superseded for named subset|
|volatility_scaled_depth_flow_momentum_control_v1|FAILED|356|-238.6907|-1.1056|-253.9681|convergence42: explicit deep-loss subset, >=100 terminal tokens/loss>=200U/recent enrollment/no pairing or contamination records; prior mean -1U filter intentionally superseded for named subset|
|issuance_holder_distribution_5u_v1|FAILED|32|-14.5117|-0.3743|-13.7937|convergence67: >=30 terminals and zero winners; negative costs-after evidence; preserve shared collectors/parent/history/exits|
|l0_continuation_failure_candidate_v1|FAILED|171|-983.6997|-2.1805|-1072.9748|user_requested_retirement_equity_below_50_of_1000|
|l0_continuation_failure_control_v1|FAILED|147|-984.0406|-2.5488|-1073.3157|user_requested_retirement_equity_below_50_of_1000|
|l0_profit_lock_candidate_v1|FAILED|243|-997.5691|-2.5156|-1150.4558|user_requested_retirement_equity_below_50_of_1000|
|l0_profit_lock_control_v1|FAILED|236|-970.8993|-1.7919|-1081.7425|user_requested_retirement_equity_below_50_of_1000|
|clone_liquidity_leader_v1|ACTIVE|4|4.7022|1.8350|-1.0361|Active|
|clone_m5volume_leader_v1|ACTIVE|2|1.0322|0.5161|UNKNOWN|Active|
|observed_set_relative_resilience_candidate_v1|ACTIVE|1|-0.3846|-0.3846|UNKNOWN|Active|
|observed_set_relative_resilience_control_v1|FAILED|340|-125.9184|-0.3850|-174.3031|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|clone_liquidity_handoff_v1|ACTIVE|0|0.0000|UNKNOWN|UNKNOWN|Active|
|staged_probe_20u_once_control_v1|FAILED|267|-982.5718|-4.0360|-1183.8783|user_requested_retirement_equity_below_50_of_1000|
|staged_probe_5u_only_control_v1|FAILED|1135|-995.7416|-0.6178|-1080.8484|convergence54: material realized loss with >=30 unique terminal tokens; depleted or failed evidence; preserve exits/history; no replacement|
|staged_probe_5u_conditional_15u_shadow_v1|FAILED|1135|-995.7416|-0.6178|-1080.8484|convergence54: material realized loss with >=30 unique terminal tokens; depleted or failed evidence; preserve exits/history; no replacement|
|mature_new_acceptance_5u_v1|ACTIVE|1|-0.2138|-0.2138|UNKNOWN|Active|
|watched_wallet_distribution_candidate_v1|FAILED|545|-356.8648|-0.3846|-434.7818|convergence42: explicit deep-loss subset, >=100 terminal tokens/loss>=200U/recent enrollment/no pairing or contamination records; prior mean -1U filter intentionally superseded for named subset|
|watched_wallet_distribution_control_v1|FAILED|545|-356.8648|-0.3846|-434.7818|convergence42: explicit deep-loss subset, >=100 terminal tokens/loss>=200U/recent enrollment/no pairing or contamination records; prior mean -1U filter intentionally superseded for named subset|
|watched_wallet_confirmed_entry_candidate_v1|DATA_BLOCKED|0|0.0000|UNKNOWN|UNKNOWN|convergence64: DATA_INPUT_BLOCKED; zero full-period positions/decisions; no recent ready; explicit input repair/new forward version required; no threshold relaxation|
|watched_wallet_confirmed_entry_control_v1|FAILED|404|-309.4383|-0.3417|-376.4562|convergence42: explicit deep-loss subset, >=100 terminal tokens/loss>=200U/recent enrollment/no pairing or contamination records; prior mean -1U filter intentionally superseded for named subset|
|finalist_boundary_retest_v1|INSUFFICIENT|10|-14.6475|-1.2268|-20.2181|convergence74: reviewed negative economics or completed S1 same-fill horizon comparison; close whole mandatory pair without replacement; preserve shared collectors/parent/history/exits|
|finalist_seller_absorption_v1|INSUFFICIENT|19|-14.3904|-1.0148|-16.0503|convergence74: reviewed negative economics or completed S1 same-fill horizon comparison; close whole mandatory pair without replacement; preserve shared collectors/parent/history/exits|
|finalist_price_then_depth_v1|DATA_BLOCKED|0|0.0000|UNKNOWN|UNKNOWN|convergence64: DATA_INPUT_BLOCKED; zero full-period positions/decisions; no recent ready; explicit input repair/new forward version required; no threshold relaxation|
|finalist_baseline_v1|FAILED|281|-344.9976|-1.1003|-432.8720|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|finalist_profit_budget_v1|FAILED|281|-329.9586|-1.0578|-417.8329|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|finalist_progress_clock_v1|FAILED|281|-199.4664|-0.3854|-287.3408|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|finalist_depth_divergence_v1|FAILED|281|-344.9976|-1.1003|-432.8720|current matched terminal paths add zero or negligible economic distinction; recommendation only|
|finalist_activity_failure_v1|FAILED|281|-345.4248|-1.1003|-433.2992|current matched terminal paths add zero or negligible economic distinction; recommendation only|
|round2_chase_control_v1|FAILED|539|-712.7267|-1.0688|-775.4841|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|round2_chase_candidate_v1|FAILED|425|-563.3500|-1.0385|-618.4395|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|round2_slow_grace_control_v1|FAILED|321|-230.5812|-0.3846|-290.0550|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|round2_slow_grace_candidate_v1|FAILED|321|-230.5340|-0.3846|-290.0079|current matched terminal paths add zero or negligible economic distinction; recommendation only|
|round2_giveback_duration_control_v1|FAILED|544|-719.9305|-1.0358|-782.6879|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|round2_giveback_duration_candidate_v1|FAILED|544|-724.5204|-1.0544|-787.2778|convergence37: 100 independent terminals, material negative expectancy, recent enrollment, negative post-P0 cohort; no contamination/void records|
|round2_response_exhaustion_control_v1|FAILED|248|-339.4599|-1.1441|-399.1121|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|round2_response_exhaustion_candidate_v1|FAILED|248|-339.4599|-1.1441|-399.1121|current matched terminal paths add zero or negligible economic distinction; recommendation only|
|round2_runner_requalification_control_v1|FAILED|247|-319.3280|-1.1384|-348.5250|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|round2_runner_requalification_candidate_v1|FAILED|247|-321.3379|-1.1384|-350.5349|current matched terminal paths add zero or negligible economic distinction; recommendation only|
|resource_age_rate_control_v1|FAILED|323|-93.3103|-1.0389|-350.3424|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|resource_age_rate_candidate_v1|ACTIVE|154|558.5533|-0.4081|260.0834|Active|
|resource_cooling_hold_control_v1|FAILED|209|-96.9000|-1.0127|-143.8841|convergence48: >=30 independent terminal tokens and material negative realized PnL; failed paired-group closure preserved; no new Paper enrollment|
|resource_cooling_hold_candidate_v1|ACTIVE|52|5.8426|-1.0032|-25.2759|Active|
|resource_profit_structure_control_v1|INSUFFICIENT|36|-23.3441|-0.3284|-41.4799|convergence63: required paired sibling paused; cannot independently enroll; preserve exits/history|
|resource_profit_structure_candidate_v1|FAILED|36|-22.9156|-0.3284|-41.0513|current matched terminal paths add zero or negligible economic distinction; recommendation only|
|inventory_baseline_v1|DATA_BLOCKED|0|0.0000|UNKNOWN|UNKNOWN|compaction51: redundant negative economics or insufficient trajectory supply; pause entire paired group; preserve exits/history; no replacement justified|
|inventory_contraction_v1|DATA_BLOCKED|0|0.0000|UNKNOWN|UNKNOWN|compaction51: redundant negative economics or insufficient trajectory supply; pause entire paired group; preserve exits/history; no replacement justified|
|inventory_cost_space_v1|FAILED|69|-70.6669|-1.3254|-82.5186|convergence33: replicated >=50 terminals and negative costed realized PnL|
|archive_drift_v1|FAILED|89|-14.3403|-1.0959|-85.7927|compaction51: redundant negative economics or insufficient trajectory supply; pause entire paired group; preserve exits/history; no replacement justified|
|archive_plateau_v1|FAILED|89|-14.3403|-1.0959|-85.7927|compaction51: redundant negative economics or insufficient trajectory supply; pause entire paired group; preserve exits/history; no replacement justified|
|archive_release_v1|INSUFFICIENT|9|-8.0820|-1.0414|-6.5410|convergence70: small-sample negative distribution; no compensating tail; user-directed convergence; preserve shared collectors/parent/history/exits|
|lifecycle_baseline_v1|FAILED|282|-351.1486|-1.0470|-410.2298|convergence33: replicated >=50 terminals and negative costed realized PnL|
|lifecycle_renewal_v1|FAILED|282|-350.7761|-1.0470|-410.1440|convergence33: replicated >=50 terminals and negative costed realized PnL|
|lifecycle_failed_rebound_v1|FAILED|282|-351.1486|-1.0470|-410.2298|convergence33: replicated >=50 terminals and negative costed realized PnL|
|lifecycle_giveback_area_v1|FAILED|282|-305.6974|-1.0334|-358.3505|convergence33: replicated >=50 terminals and negative costed realized PnL|
|lifecycle_risk_trim_v1|FAILED|282|-348.7435|-1.0358|-407.8246|convergence33: replicated >=50 terminals and negative costed realized PnL|
|lifecycle_probe_v1|FAILED|282|-351.1486|-1.0470|-410.2298|convergence33: replicated >=50 terminals and negative costed realized PnL|
|runner_capture_v1|FAILED|167|-287.1117|-2.2958|-341.0184|convergence33: replicated >=50 terminals and negative costed realized PnL|
|runner_capture_legacy_exit_control_v1|FAILED|167|-177.6611|-1.1588|-221.0188|convergence33: replicated >=50 terminals and negative costed realized PnL|
|quiet_renewal_v1|ACTIVE|9|-1.1347|-1.3729|-11.2801|Active|
|quiet_renewal_legacy_exit_control_v1|ACTIVE|9|-0.5778|-0.5155|-6.2215|Active|
|early_impulse_control_15m_v1|FAILED|69|-63.3094|-1.0229|-85.1544|compaction51: redundant negative economics or insufficient trajectory supply; pause entire paired group; preserve exits/history; no replacement justified|
|early_impulse_trailing_60m_v1|FAILED|69|-9.9396|-1.0697|-86.0229|compaction51: redundant negative economics or insufficient trajectory supply; pause entire paired group; preserve exits/history; no replacement justified|
|early_impulse_probation_60m_v1|FAILED|69|-9.9396|-1.0697|-86.0229|compaction51: redundant negative economics or insufficient trajectory supply; pause entire paired group; preserve exits/history; no replacement justified|
|early_impulse_profit_lock_control_v1|DUPLICATE_SUPERSEDED|47|18.5626|-0.7567|-57.5207|convergence37: end failed profit-lock paired experiment; retain original trailing group|
|early_impulse_profit_lock_40_v1|FAILED|47|-6.7980|-0.7567|-47.7831|convergence37: end failed profit-lock paired experiment; retain original trailing group|
|runner_ultra_early_control_v1|INSUFFICIENT|6|-10.6115|-0.9714|-11.3845|compaction51: redundant negative economics or insufficient trajectory supply; pause entire paired group; preserve exits/history; no replacement justified|
|runner_ultra_early_lock_v1|INSUFFICIENT|6|-9.4420|-0.9714|-11.3845|compaction51: redundant negative economics or insufficient trajectory supply; pause entire paired group; preserve exits/history; no replacement justified|
|age_rate_horizon_fast_v1|EXPERIMENT_COMPLETE_POSITIVE|33|101.7183|-0.3036|25.5428|convergence74: reviewed negative economics or completed S1 same-fill horizon comparison; close whole mandatory pair without replacement; preserve shared collectors/parent/history/exits|
|age_rate_horizon_runner_v1|FAILED|33|-12.5757|-0.2938|-32.9598|convergence74: reviewed negative economics or completed S1 same-fill horizon comparison; close whole mandatory pair without replacement; preserve shared collectors/parent/history/exits|

Artifacts: data/research/lifecycle89/frozen.json,live.json,result.json,trade_reconciliation.json,applied.json. Complete per-arm metrics include distinct tokens, open counts, PF, extrema, causes and hashes. scripts/research_lifecycle89.py reproduces the offline classification/common-fill analysis; scripts/apply_lifecycle89.py applies display metadata with exact frozen-control precondition.
