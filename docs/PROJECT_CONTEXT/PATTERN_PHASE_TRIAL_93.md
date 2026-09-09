# Pattern initial-phase trial93

REPLY_TO: C2C-20260909-PATTERN-PHASE-STAGGER-93
Disposition: ACCEPT_BOUNDED_TRIAL_NO_SPEEDUP_CLAIM.

Only initial start shifts: observer0s, pools5s, participation10s; all retain15s scheduling. Stop-aware initial wait; held primary/SELL/decision and every other task remain immediate. No targets, capacity, API budget, entry/exit semantics or thresholds changed. Initial pool verification is delayed5s, participation10s as intended; this does not gate the independent primary held/SELL work. This is initial staggering, not a permanent phase-lock: overruns may cause drift.

Validation: six targeted scheduler/decision tests passed (five on first run, wiring fixture updated for keyword then passed). Real loop test proves three calls at unchanged1s intervals with only first start shifted; stop-before-first-start prevents action. Wiring asserts only the two intended tasks receive phase values. Diff check PASS.

Trial loaded2026-09-09T10:45:55Z. Comparable short startup windows: baseline10:42:34–10:45:36; trial10:45:55–10:49:16. Aggregate rolling120 held samples; pattern approximately12cycles, not sustained/controlled performance proof. Natural target/network workload can differ.

|Task|samples before/after|duration p95 before(s)|after(s)|after interval p95(s)|
|---|---:|---:|---:|---:|
|held_fetch|120/120|2.3700|1.9358|None|
|held_apply_exit|120/120|0.0930|0.0881|None|
|chain_meme_pattern_observer|11/13|7.4738|7.0780|15.330091635001736|
|chain_meme_pattern_pools|11/13|6.8506|8.7830|15.412306185002672|
|chain_meme_pattern_participation|11/13|4.8712|2.0045|15.43443174999993|

Before: passive drops=0, wait p95=2.0367s; Dex pool_timeouts=0, connect_errors=0; held tokens at read=0.

After: passive drops=0, wait p95=2.0041s; Dex pool_timeouts=0, connect_errors=0; held tokens at read=1.

Held p95 regression guards not crossed, no passive drops, configured15s unchanged and actual cadence remains near15s. Pool duration worsened while participation improved; net resource benefit is not established. No claim of higher provider throughput. Functions/targets and budgeting remain unchanged; this trial did not instrument every provider-start count.

Health running, Paper/live_locked preserved. Seven-table contract/funding digest unchanged5883a315353ee88e25bf6090c69bf7b216c0804145a7a6822922b776c3723980. No reset/backfill. Existing admission audit84 remains discontinuous (805pre/1066post process-local dropped audit records), distinct from the zero-drop passive trading queue; not repaired or used as a complete denominator here.

Evidence: data/research/admission88/pre93.json, post93-final.json (intermediate trial93-mid/post93 retained). Rollback is limited to initial-delay scheduler keyword and two task call sites if later adverse evidence appears. No automatic monitoring or periodic restart installed.
