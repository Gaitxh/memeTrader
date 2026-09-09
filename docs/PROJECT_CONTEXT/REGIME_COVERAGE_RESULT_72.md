# Regime discovery coverage72

REPLY_TO: C2C-20260909-REGIME-SHADOW-COVERAGE-72
Disposition: IMPLEMENTED_REPORT_ONLY

Smallest change to existing report:adaptive disjoint discovery primary-key tails10000->20000->40000 cap, stop when earliest retained recorded_at reaches prior15m window start. Older ranges fetched once, chronological ID order maintained, no duplicated rows. Market/evidence limits, all metrics, missingness,20-receipt minimum and no-outcome contract unchanged. Existing total3s SQLite progress callback applies to expansions too. Interrupted SQL emits UNKNOWN/sqlite_3s_budget_exceeded/report_written=false and nonzero exit; no partial success report. Existing output file if any is not updated and must not be treated as fresh; callers should use cutoff-specific filenames. No scheduler or runtime consumer.

Actual r6 cutoff2026-09-09T04:57:50.271980Z:20000 discovery+12000market+10000evidence rows,1.793398s. Both adjacent15m windows covered. Local receipt intensity ratios:SOLS1.212355,BSC1.356725,RH1.420290,Four1.163522,LaunchLab1.35;Pons and pregrad event-only group remain UNKNOWN for insufficient receipt denominator. These are observed local supply ratios, not HOT/COLD, chainwide volume, Alpha or allocation instruction. No output PnL/ATH.

3 targeted tests PASS:future frame/missing activity/truncation UNKNOWN;unique migration-event dedupe;adaptive boundary/disjoint IDs/hard-cap stop. git diff check PASS. No runtime restart, production SQLite write, strategy/funding/history/Live changes. Absolute workload may vary;3s interruption still fails closed,40000 cap never expands unboundedly. No p95 claim from one run.

Artifacts data/research/regime72/state.json; scripts/report_regime_shadow_v2.py;tests/test_regime_shadow_v2.py. No temporal cache/replay or change in prior frozen62 file.
