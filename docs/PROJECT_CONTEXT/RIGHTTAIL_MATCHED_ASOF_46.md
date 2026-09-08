# ACTIVE16 matched as-of pilot46

Research resumed after connection-pool LONG_RUN_PASS. Production SQLite read-only, no restart or strategy mutation.

Selected up to5 controls per available case anchor from preceding10000 snapshot IDs: same UTC date/chain/provider; pool age within max(60s,25%); price>0/liquidity>=1000; observed<=ingested<=recorded and control recorded<=case recorded. Require control first valid local token frame, exclude all16 case IDs, choose most recent eligible independently of future outcome. This is a bounded pilot, not a full-day denominator or causal estimator. Anchor pointers reused from independently checked casebook; absence/earliest claims remain bounded by previous evidence.

16 cases processed;9 cases matched to40 distinct control tokens;7 lack valid feature anchor or bounded matches. Controls are UNLABELLED, not presumed failures. Remaining work includes strict next exact-pool entry, future coverage/censoring, failure/ordinary labels, actual entry/exit attribution and full-date match coverage. No Alpha/strategy inference yet. Selection does not use future MFE; the user-selected cases themselves remain ex-post selected and cannot measure precision.

Illustrative stored as-of differences: d270 trades7 vs control median1; build70 vs1; e2322298 vs1; but O1BOT191 vs610 (only1 match). Build buy share.386 vs.6; d270.429 vs1.0. Thus these pairs do not support requiring majority buys as a universal precursor. Activity distinctions are descriptive; sparse/zero controls and differing liquidity still confound. Derived ratios currently coalesce missing activity to0: they cannot distinguish measured zero from missing, and must be audited before model use. No thresholds selected. Separate post-fix19:51:47+ source cohorts from S1 disturbed19:06–19:51:47; this historical pilot does not constitute post-fix economic validation.

Artifacts: data/research/user_righttail_cases_20260908/matched_asof46.json and matched_asof46_features.json (exact row IDs and frozen matching definition).
