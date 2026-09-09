# Today23 strict-forward casebook78

REPLY_TO: C2C-20260909-TODAY-RIGHTTAIL-23-78. Frozen cutoff 2026-09-09T06:49:35Z. Research only; no registration/production mutation.

## Summary

{"addresses": 23, "found": 21, "missing": ["0x87359b7d78b03bd81b567bf425263b453c73eeee", "0xc26e887d361a67226fa2903375ccd312e2bb7777"], "stages": {"NO_VALID_FLOOR_ANCHOR": 4, "ACTUAL_BUY": 6, "NO_STRICT_NEXT": 4, "NO_PATTERN_EVALUATION_RECORDED": 4, "EVALUATED_NO_BUY": 3}, "matched_cases": 8, "control_rows": 22, "first_hit100": {"NO_ENTRY": 8, "STOP_FIRST": 4, "UNKNOWN_NO_HIT": 6, "UNKNOWN_GAP": 3}, "parent_capture": 5, "reawakening_capture": 0, "endpoint6h": 2}

## Method and limits

Exact address lookup across configured BSC/Robinhood/Solana plus Ethereum/Base;21 local identities,2 unmatched in this lookup (not proof of nonexistence onchain). No address padding, name matching or whitelist. 4s SQLite query budget, bounded per-token rows; final extraction has zero query interruptions. First attempt used an unindexed address query and was cancelled by that budget, then replaced with primary-key lookups. Snapshot limit20001 was not reached. GME20 pattern evaluations reached2001; gate counts are its earliest bounded prefix, not full-period rates.

All market frames verify base token/chain/exact pool and observed<=ingested<=recorded<=cutoff; raw missing activity remains null, distinct from zero. Quote/dex labels are provider descriptors, not authenticated launch provenance. Original pool means first locally valid pool, not first-ever chain pool. Alternative pools remain separate episodes, never implicit successor authorization. First buy hypothesis uses a strictly later frame after anchor recording. Future accepted states are causal;4%/4% proxy; MFE is sampled lower bound, not realized profit. 15m/60m/6h endpoints require horizon..horizon+120s. Missing endpoints remain UNKNOWN. First-hit75 uses60m and labels gaps>120s UNKNOWN; explicit below-floor states are additionally retained as floor_first, and must precede any claimed later positive path. No missing liquidity or missing frame is a death.

Positions use existing actual ledger entries, current status is censored if closed after cutoff; partial realized cashflows on still-open positions are not reconstructed and total is terminal-only. Mutable token.source is not backdated to first receipt; earliest recorded discovery exposure is retained. Current active policy set is read-time, not a reconstruction of historical policy activation. Actual historical gates and BUYs establish what was observed; this is not a counterfactual claim that today’s code would buy at every old frame.

## Per-case original-pool path

|Token/symbol|First missing stage|Strict-next delay s|6h sampled max net|First100 vs stop (60m)|First BUY delay s|Terminal PnL U across all old arms|
|---|---|---:|---:|---|---:|---:|
|うさぎ `bsc:0x113d68c8cca4fe5ba25f49c00784079d168e7777`|NO_VALID_FLOOR_ANCHOR|None|UNKNOWN%|NO_ENTRY|None|0.000000|
|TICKR `bsc:0x320474b5f11b030407b7e7bd5f5a989c730a0000`|ACTUAL_BUY|92.33379006385803|9838.520681570655%|STOP_FIRST|784.9554390907288|-0.439428|
|Hock `bsc:0x43330ef84f7f226c32562463dfd7442461907777`|NO_STRICT_NEXT|None|UNKNOWN%|NO_ENTRY|None|0.000000|
|BITCAT `bsc:0x7d1a8dbb40b7b5518ef69b93a6faeba91eea7777`|NO_PATTERN_EVALUATION_RECORDED|90.27480602264404|UNKNOWN%|UNKNOWN_NO_HIT|None|0.000000|
|LAPTOP `bsc:0x9cd3a3eed3e4a2c832590dd59aa8c3f657bd8888`|NO_VALID_FLOOR_ANCHOR|None|UNKNOWN%|NO_ENTRY|None|0.000000|
|GME20 `bsc:0xba4e0404a1169a03429e1d06c1e8ecd6b61d7777`|ACTUAL_BUY|8870.335314035416|95.13213002846794%|UNKNOWN_GAP|13209.356742858887|-17.235263|
|企飞 `bsc:0xd5eeb6104796eca13899fbd69400630905247777`|NO_STRICT_NEXT|None|UNKNOWN%|NO_ENTRY|None|0.000000|
|PYRE `robinhood:0x0d11e308e40c15e1181aed4f4bbfc4744e9deeed`|ACTUAL_BUY|42.84502100944519|7.99249530956847%|UNKNOWN_GAP|586.412260055542|3.589729|
|Jacob `robinhood:0x3df3644bcf4ce0d993e18c86c3080e53bfea06f1`|EVALUATED_NO_BUY|89.68074107170105|UNKNOWN%|UNKNOWN_NO_HIT|None|0.000000|
|CLAWDHOOD `robinhood:0x50ec3b65691a911be049cd0d2d6e639cd1cfdb9b`|NO_PATTERN_EVALUATION_RECORDED|91.5574688911438|-13.415551655260217%|UNKNOWN_GAP|None|0.000000|
|DUO `robinhood:0x56aaa501fa9eb6670d6175d686957434c3d21e18`|ACTUAL_BUY|27.367328882217407|53.55029585798818%|UNKNOWN_NO_HIT|27.813030004501343|-1.791395|
|CRUMBS `robinhood:0x80baa4b3bfac6f4978700df824b1b3d98e889136`|NO_PATTERN_EVALUATION_RECORDED|98.39928603172302|7.239819004524883%|STOP_FIRST|None|0.000000|
|AITAX `robinhood:0xb244edd7674d0969fe63ceaa3d4a2ed69f397db0`|EVALUATED_NO_BUY|1.9760000705718994|19.645706990105328%|UNKNOWN_NO_HIT|None|0.000000|
|QUEST `robinhood:0xb429a196034128e652b116b1525b856294dd98b3`|EVALUATED_NO_BUY|89.71312284469604|UNKNOWN%|UNKNOWN_NO_HIT|None|0.000000|
|RECEIPT `robinhood:0xb97d9e5ad6244d27588fe0a624a8c78e512934ee`|ACTUAL_BUY|46.954336166381836|71.30025097970143%|STOP_FIRST|48.840344190597534|-13.840749|
|PARLEY `robinhood:0xcf3d41f9671dc2e86ee4c0271b79ae6fdce36c05`|ACTUAL_BUY|44.02968692779541|46.83828361677915%|STOP_FIRST|44.765925884246826|-17.563254|
|CRIMECAT `solana:4oWhtcmBBsMG1bLZCLKusmq4t9fxdVVfbyJLevsYg5Ct`|NO_PATTERN_EVALUATION_RECORDED|21587.476560115814|UNKNOWN%|UNKNOWN_NO_HIT|None|0.000000|
|METH `solana:6CsmCtDAhRcbp3G4KiinKC2JjLJ9BpR7isqcgZefqLym`|NO_VALID_FLOOR_ANCHOR|None|UNKNOWN%|NO_ENTRY|None|0.000000|
|Mooncoin `solana:9RdsqgqtfkFkteNcWSu27wDGKcn6A9hTXoVet6TfS5H4`|NO_VALID_FLOOR_ANCHOR|None|UNKNOWN%|NO_ENTRY|None|0.000000|
|tip `solana:Fhxcx7cHmhDkfwziHyCwN8vQRvEFRK3zezokaE8gL5q7`|NO_STRICT_NEXT|None|UNKNOWN%|NO_ENTRY|None|0.000000|
|MUCHWOW `solana:GLRyB95LzCyyY8TVfwZVDyrVcZuSJPJJoaPTnyWs89mv`|NO_STRICT_NEXT|None|UNKNOWN%|NO_ENTRY|None|0.000000|

Missing exact addresses: 0x87359b7d78b03bd81b567bf425263b453c73eeee, 0xc26e887d361a67226fa2903375ccd312e2bb7777.

## Current survivors and actual gates

- うさぎ: parent first=None; parent BUYs=0; reawakening first=None; reawakening BUYs=0.
- TICKR: parent first={'id': 1203846, 'snapshot': 2008400, 'at': '2026-09-08T19:59:42.111556Z', 'reason': 'resource_no_comparable_positive_baseline', 'pool': '0x99219a385ec01ed3b2a422dbc1c5a988ef3461c6'}; parent BUYs=0; reawakening first={'id': 1203846, 'snapshot': 2008400, 'at': '2026-09-08T19:59:42.111556Z', 'reason': 'replacement_pool_age_not_met', 'pool': '0x99219a385ec01ed3b2a422dbc1c5a988ef3461c6'}; reawakening BUYs=0.
- Hock: parent first=None; parent BUYs=0; reawakening first=None; reawakening BUYs=0.
- BITCAT: parent first=None; parent BUYs=0; reawakening first=None; reawakening BUYs=0.
- LAPTOP: parent first=None; parent BUYs=0; reawakening first=None; reawakening BUYs=0.
- GME20: parent first={'id': 1191757, 'snapshot': 1996305, 'at': '2026-09-08T18:38:05.823332Z', 'reason': 'resource_old_rate_below_threshold', 'pool': '0x34a638b2f1fd453e544c3ddff06b72ce5f7f3dca'}; parent BUYs=1; reawakening first={'id': 1191757, 'snapshot': 1996305, 'at': '2026-09-08T18:38:05.823332Z', 'reason': 'awaiting_replacement_l0_sequence', 'pool': '0x34a638b2f1fd453e544c3ddff06b72ce5f7f3dca'}; reawakening BUYs=0.
- 企飞: parent first={'id': 1120540, 'snapshot': 1924989, 'at': '2026-09-08T14:19:28.844919Z', 'reason': 'resource_old_rate_below_threshold', 'pool': '0x948c40eecb43bb0aed66d2e4b3b7e317b75514aa'}; parent BUYs=0; reawakening first={'id': 1120540, 'snapshot': 1924989, 'at': '2026-09-08T14:19:28.844919Z', 'reason': 'awaiting_replacement_l0_sequence', 'pool': '0x948c40eecb43bb0aed66d2e4b3b7e317b75514aa'}; reawakening BUYs=0.
- PYRE: parent first={'id': 1255561, 'snapshot': 2060122, 'at': '2026-09-08T22:33:00.152669Z', 'reason': 'resource_old_rate_below_threshold', 'pool': '0x51110343d68775f5c9f90075901fc4a4d7b427bdc75bf85bd8f93623f834e866'}; parent BUYs=1; reawakening first={'id': 1255561, 'snapshot': 2060122, 'at': '2026-09-08T22:33:00.152669Z', 'reason': 'awaiting_replacement_l0_sequence', 'pool': '0x51110343d68775f5c9f90075901fc4a4d7b427bdc75bf85bd8f93623f834e866'}; reawakening BUYs=0.
- Jacob: parent first={'id': 1385244, 'snapshot': 2189813, 'at': '2026-09-09T04:43:01.395672Z', 'reason': 'resource_age_rate_common_wait', 'pool': '0xe74f520425b300805f0f803239a56079ede772a94855bd3576f1db2d249a919e'}; parent BUYs=0; reawakening first={'id': 1385244, 'snapshot': 2189813, 'at': '2026-09-09T04:43:01.395672Z', 'reason': 'replacement_pool_age_not_met', 'pool': '0xe74f520425b300805f0f803239a56079ede772a94855bd3576f1db2d249a919e'}; reawakening BUYs=0.
- CLAWDHOOD: parent first=None; parent BUYs=0; reawakening first=None; reawakening BUYs=0.
- DUO: parent first={'id': 759095, 'snapshot': 1563090, 'at': '2026-09-07T14:47:36.509674Z', 'reason': 'resource_old_rate_below_threshold', 'pool': '0x60e7d9e82a208f501f020f84d2ec47401837ad5993ac7faae893021434170347'}; parent BUYs=1; reawakening first={'id': 759095, 'snapshot': 1563090, 'at': '2026-09-07T14:47:36.509674Z', 'reason': 'awaiting_replacement_l0_sequence', 'pool': '0x60e7d9e82a208f501f020f84d2ec47401837ad5993ac7faae893021434170347'}; reawakening BUYs=0.
- CRUMBS: parent first=None; parent BUYs=0; reawakening first=None; reawakening BUYs=0.
- AITAX: parent first={'id': 1202658, 'snapshot': 2007212, 'at': '2026-09-08T19:55:52.026883Z', 'reason': 'resource_old_rate_below_threshold', 'pool': '0x27a5372dcb5a6fff92d334a6e07c8ff3417b69c918257050b76eadc7333c856f'}; parent BUYs=0; reawakening first={'id': 1202658, 'snapshot': 2007212, 'at': '2026-09-08T19:55:52.026883Z', 'reason': 'awaiting_replacement_l0_sequence', 'pool': '0x27a5372dcb5a6fff92d334a6e07c8ff3417b69c918257050b76eadc7333c856f'}; reawakening BUYs=0.
- QUEST: parent first={'id': 1420429, 'snapshot': 2224998, 'at': '2026-09-09T06:22:50.177375Z', 'reason': 'resource_age_rate_candidate_rejected', 'pool': '0xae0b8c8f93ea9cc3600575ed6c60086b12b64badeaa94bb50c75443c1bc36e7e'}; parent BUYs=0; reawakening first={'id': 1420429, 'snapshot': 2224998, 'at': '2026-09-09T06:22:50.177375Z', 'reason': 'replacement_pool_age_not_met', 'pool': '0xae0b8c8f93ea9cc3600575ed6c60086b12b64badeaa94bb50c75443c1bc36e7e'}; reawakening BUYs=0.
- RECEIPT: parent first={'id': 1144534, 'snapshot': 1949025, 'at': '2026-09-08T15:37:52.272976Z', 'reason': 'resource_age_rate_ready', 'pool': '0xab43aa8870ba31a89d744dc53136fc6835eb0f2dd319995bcefcd2fe2463b6c0'}; parent BUYs=1; reawakening first={'id': 1144534, 'snapshot': 1949025, 'at': '2026-09-08T15:37:52.272976Z', 'reason': 'replacement_pool_age_not_met', 'pool': '0xab43aa8870ba31a89d744dc53136fc6835eb0f2dd319995bcefcd2fe2463b6c0'}; reawakening BUYs=0.
- PARLEY: parent first={'id': 775377, 'snapshot': 1579448, 'at': '2026-09-07T16:25:32.176783Z', 'reason': 'resource_age_rate_common_wait', 'pool': '0xb749d03a2000e8189fdc9412507ac60f83cca2aac351157cc6a139cfd7055705'}; parent BUYs=1; reawakening first={'id': 775377, 'snapshot': 1579448, 'at': '2026-09-07T16:25:32.176783Z', 'reason': 'replacement_pool_age_not_met', 'pool': '0xb749d03a2000e8189fdc9412507ac60f83cca2aac351157cc6a139cfd7055705'}; reawakening BUYs=0.
- CRIMECAT: parent first=None; parent BUYs=0; reawakening first=None; reawakening BUYs=0.
- METH: parent first=None; parent BUYs=0; reawakening first=None; reawakening BUYs=0.
- Mooncoin: parent first=None; parent BUYs=0; reawakening first=None; reawakening BUYs=0.
- tip: parent first={'id': 1358125, 'snapshot': 2162694, 'at': '2026-09-09T03:23:06.618696Z', 'reason': 'resource_old_rate_below_threshold', 'pool': 'HaQvS9tCTJoSc9Tp3TbgwM183TMKYjq8obxNNdeB6UD2'}; parent BUYs=0; reawakening first={'id': 1358125, 'snapshot': 2162694, 'at': '2026-09-09T03:23:06.618696Z', 'reason': 'awaiting_replacement_l0_sequence', 'pool': 'HaQvS9tCTJoSc9Tp3TbgwM183TMKYjq8obxNNdeB6UD2'}; reawakening BUYs=0.
- MUCHWOW: parent first=None; parent BUYs=0; reawakening first=None; reawakening BUYs=0.

Whole original-pool peak through cutoff is separately stored in analysis.json (whole_original_pool_peak_to_cutoff). Peaks after6h do not describe the initial6h opportunity or authorize later re-entry. Full per-arm gates, each actual entry/exit/pool/PnL, source row IDs, as-of features, native facts and all alternative-pool episodes: data/research/today23_78/casebook.json and analysis.json.

## Controls and earlier evidence

Outcome-blind controls reuse the completed71 frozen dataset (cutoff04:55:14Z/frontier2194123), never rescan market winners. Fixed same date/chain/provider/age-band/liquidity0.5–2x/quote, rank age/liquidity/time, earlier available anchor only; exclude all23 cases. Up to3 controls with reuse explicit. Native provenance is not independently matched; these are provisional diagnostics, not sufficient strategy controls. Sep9 control outcomes in71 intentionally remain unevaluated. Today’s ex-post cases are not a holdout validation set.

Compared with old16 strict-surface38: both show that first seen, same-token chart rise, exact-pool executable evidence and actual fill are different stages. Old16 reported14 anchors and missing strict second rows for RSTR/ROUTE/PUG/500; no claim these counts share today’s cutoff or sample distribution. Universe71 Sep8 original24748->strict entries9380->60m paths3542->endpoints153; its broad denominator already demonstrates severe sampling attrition. Today’s case study cannot estimate precision or prove a new signal against that universe.

## Disposition

RESEARCH_ONLY / INSUFFICIENT_CAUSAL_COVERAGE. No1–2 strategy arms registered. Parent remains champion77; no fast replacement. Data continuity/identity supply remains first priority, but absent frames alone does not prove a local scheduler bug: no production change is justified without queue/provider/admission trace. Native provenance is only established where actual launch facts exist; Pons/Flap/Raydium labels alone do not authenticate Classic/OpenFour/PonsV2/LaunchLab. Native economics proof76 remains unresolved. No thresholds searched, no retrospective strategy mutation, no funding/reset/history rewrite/Live.

## Specific findings and verification

- TICKR original-pool sampled max is+9838.52%, but the60m first-hit ordering is STOP_FIRST. Parent did not buy: its recorded outcomes include101 open-slot-limit observations, one candidate rejection and1115 already-consumed opportunity outcomes. This proves recorded gate/admission loss, not that loosening the rule is profitable or that capacity alone caused the miss. Prebreakout did buy; all historical arms combined terminal PnL-0.439428U (not independent strategy samples).
- Parent actually captured GME20(-1.492915U hard stop), PYRE(+0.558488U max hold), DUO(-0.791152U max hold), RECEIPT(+1.860112U trailing), PARLEY(-1.076883U hard stop). These selected-case results do not overturn the common-fill champion77 comparison or estimate all-market expectancy.
- Hock has only1 valid snapshot; BITCAT and CRIMECAT have a strict-next but no subsequent original-pool valid return frame within6h. QUEST/Jacob show provider-labelled Pons surfaces and multiple pools; official migration/instance identity is not inferred from those labels. No arbitrary surface stitching.
- CRIMECAT and Mooncoin have actual PumpPortal launch facts; Mooncoin has no valid floor-qualified market anchor. No retained native economics row establishes an OBSERVED valid5U/20U curve model for this23. Other launchpad categories remain UNKNOWN without verified facts; token suffix/dex label is insufficient.
- Today23 is ex-post selected; only8 cases have22 provisional frozen71 control rows, reused and not native-provenance matched. Sparse same-pool paths, missing identities, and cutoff differences prevent a new independent Alpha conclusion. No new failure family is claimed: existing starvation, execution/path-order and identity/provenance lessons explain the observed limitations.

Validation:5 targeted tests passed (identity, future clocks, floor evidence retention, missing-vs-zero, exact23 list, first-hit causal order/gaps). Artifact assertions passed across10039 selected source snapshots and55 exact-pool episodes. No full-market production rescan, no Store instantiation, no database writes, no runtime restart. Python scripts only generate research artifacts.
