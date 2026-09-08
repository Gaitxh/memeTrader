# Strategy convergence 33 — current execution result

Status: IN_PROGRESS. Exact reply to C2C-20260909-STRATEGY-FORWARD-CONVERGENCE-33. This record distinguishes implementation, deployment and evidence gates.

## Completed first stage

At 2026-09-08T18:19:14Z the existing convergence KV was merged to pause NEW entries for runner_capture and legacy control, six lifecycle arms and inventory_cost_space. All nine independently reproduced >=50 terminals and negative costed realized PnL. Existing control entries preserved. Same-transaction position/trade SHA256 unchanged, no funding or history updates. Evidence: data/research/strategy_convergence_20260909/freeze_applied.json (includes previous control for audit).

Runner losses -287.112/-177.661U on 167 tokens; lifecycle terminal losses -303.594 to -349.239U with 278 terminals; inventory_cost_space -66.162U on 68 terminals. Open lifecycle/inventory positions remain eligible for ordinary exits. Existing queued-buy retirement regression PASS.

Inventory baseline/contraction are not yet frozen: their 1902 recent outcome rows per arm include 872 unavailable/surface, 241 noncausal/gap and 62 identity/source boundaries. This is concrete upstream-feature loss as well as 466 expansion waits, so zero positions is not sufficient evidence of a dead hypothesis. No threshold loosening.

Archive drift/plateau match all 75 observed entry/exit outcomes, but capital exit contracts differ. No permanent-duplicate claim or automatic retirement. Profit-lock treatment has 44 paired terminals (-0.179 vs +23.867U) and one paired OPEN. Hold new-enrollment change until shared-pair admission implications/remaining paired exit are resolved; do not silently disable its control through group-size gating.

Age-rate candidate: 97 common terminals equal +178.669642U on both arms, unmatched control 211 terminals -249.723323U. Candidate +166.982U becomes -90.049918U after top3 removal; selection evidence, not robust alpha. Frozen bounded evidence: freeze_arm_readonly_evidence_20260909.json.

## Implemented, awaiting coherent runtime deployment

Existing 20-second cached/4000-row bounded API funnel now adds distinct candidate/signal tokens, decision tokens/cohorts, BUY rows/tokens/cohorts and per-token count. UI exposes these counts. Missing linked feature/next-frame/terminal stages remain explicitly unmeasured; independent truncated ledger windows must not be presented as a complete causal funnel. Targeted web regression and JS syntax PASS.

S1 age_rate_horizon_fast_v1 / runner_v1 policy factories reuse the unchanged candidate entry, 5U/max4, hard stop -20%, trailing +30%/15%; only max hold 15/60m differs. Same-fill entry integration test PASS, original contract preserved. NOT registered in production: prerequisite P0 bridge/funnel natural progress remains pending. Main risks are sparse tail dominance, liquidity writeoff, and 8% round-trip slippage; frequency equals eligible common opportunities subject to both-arm capacity. Evaluate token-paired after-cost PnL, chain/date and top1/top3 removal before any alpha claim.

## Storage

Backup matrix from backup_inventory.json: KEEP before-position-void (unique irreversible audit), KEEP before-final-v002-funding (nearest current period recovery); KEEP before-funded-period-20260905, before-reviewed-funding and before-all122-funding pending content/frontier equivalence review. Filenames/size are not proof of duplicate recovery data; associated WAL/SHM remain together. No backup deleted or VACUUM issued.

Old root .pytest-tmp-* deletion was rejected by automatic approval policy (blocked by policy). No deletion occurred and no bypass attempted. Bytes reclaimed: 0. data/tmp and .tmp remain untouched.

## Remaining gates

P0-B Gecko exact-source bridge under independent bounded implementation/tests. No surge/capacity expansion. Natural source32-definition post-frontier coverage and held/429/drop guards are required before accepting it. P0-C conditional on residual coverage loss; S2 deferred until usable early trajectories, S3 until entry evidence supports separate dynamic exit, S4 shadow first. Matched casebook work remains in progress. No reset/backfill/Live.
