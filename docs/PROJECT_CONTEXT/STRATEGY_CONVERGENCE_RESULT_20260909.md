# Strategy convergence 33 — current execution result

Status: PARTIAL_IMPLEMENTED; BRIDGE_TRIAL_REVERTED; S2/S3 GATED. Exact reply to C2C-20260909-STRATEGY-FORWARD-CONVERGENCE-33. This record distinguishes implementation, deployment and evidence gates.

## Completed first stage

At 2026-09-08T18:19:14Z the existing convergence KV was merged to pause NEW entries for runner_capture and legacy control, six lifecycle arms and inventory_cost_space. All nine independently reproduced >=50 terminals and negative costed realized PnL. Existing control entries preserved. Same-transaction position/trade SHA256 unchanged, no funding or history updates. Evidence: data/research/strategy_convergence_20260909/freeze_applied.json (includes previous control for audit).

Runner losses -287.112/-177.661U on 167 tokens; lifecycle terminal losses -303.594 to -349.239U with 278 terminals; inventory_cost_space -66.162U on 68 terminals. Open lifecycle/inventory positions remain eligible for ordinary exits. Existing queued-buy retirement regression PASS.

Inventory baseline/contraction are not yet frozen: their 1902 recent outcome rows per arm include 872 unavailable/surface, 241 noncausal/gap and 62 identity/source boundaries. This is concrete upstream-feature loss as well as 466 expansion waits, so zero positions is not sufficient evidence of a dead hypothesis. No threshold loosening.

Archive drift/plateau match all 75 observed entry/exit outcomes, but capital exit contracts differ. No permanent-duplicate claim or automatic retirement. Profit-lock treatment has 44 paired terminals (-0.179 vs +23.867U) and one paired OPEN. Hold new-enrollment change until shared-pair admission implications/remaining paired exit are resolved; do not silently disable its control through group-size gating.

Age-rate candidate: 97 common terminals equal +178.669642U on both arms, unmatched control 211 terminals -249.723323U. Candidate +166.982U becomes -90.049918U after top3 removal; selection evidence, not robust alpha. Frozen bounded evidence: freeze_arm_readonly_evidence_20260909.json.

## Funnel deployed; S1 registered

Existing 20-second cached/4000-row bounded API funnel now adds distinct candidate/signal tokens, decision tokens/cohorts, BUY rows/tokens/cohorts and per-token count. UI exposes these counts. Missing linked feature/next-frame/terminal stages remain explicitly unmeasured; independent truncated ledger windows must not be presented as a complete causal funnel. Targeted web regression and JS syntax PASS.

S1 age_rate_horizon_fast_v1 / runner_v1 policy factories reuse the unchanged candidate entry, 5U/max4, hard stop -20%, trailing +30%/15%; only max hold 15/60m differs. Same-fill entry integration test PASS, original contract preserved. Registered at 2026-09-08T18:35:13.377833Z after the funnel/bridge loaded and natural bridge progress was observed. Activation snapshot/evaluation frontiers: fast1995513/1190965, runner1995520/1190972. Old additions and all registration/funding rows preserved. Later bridge rollback does not alter these independent age-rate arms. At the bounded 18:36–18:37 read each appeared in227 new evaluation payloads, with zero positions; no profitability conclusion. Main risks are sparse tail dominance, liquidity writeoff, and 8% round-trip slippage; frequency equals eligible common opportunities subject to both-arm capacity. Evaluate token-paired after-cost PnL, chain/date and top1/top3 removal before any alpha claim.

## Storage

Backup matrix from backup_inventory.json: KEEP before-position-void (unique irreversible audit), KEEP before-final-v002-funding (nearest current period recovery); KEEP before-funded-period-20260905, before-reviewed-funding and before-all122-funding pending content/frontier equivalence review. Filenames/size are not proof of duplicate recovery data; associated WAL/SHM remain together. No backup deleted or VACUUM issued.

Old root .pytest-tmp-* deletion was rejected by automatic approval policy (blocked by policy). No deletion occurred and no bypass attempted. Bytes reclaimed: 0. data/tmp and .tmp remain untouched.

## Remaining gates

P0-B Gecko exact-source bridge under independent bounded implementation/tests. No surge/capacity expansion. Natural source32-definition post-frontier coverage and held/429/drop guards are required before accepting it. P0-C conditional on residual coverage loss; S2 deferred until usable early trajectories, S3 until entry evidence supports separate dynamic exit, S4 shadow first. Matched casebook work remains in progress. No reset/backfill/Live.

## Independent external source verification

[CoinGecko new-pools reference](https://docs.coingecko.com/reference/latest-pools-network) currently confirms at most 20 pools/page and default page 1; slicing a response to 40 cannot create additional returned pools. The current page read did not confirm a 30-second cache promise, so that timing remains unverified here. [Multiple-pool reference](https://docs.coingecko.com/reference/pools-addresses) documents the exact-address multi-pool interface; paid CoinGecko specifications must not be assumed identical to public GeckoTerminal quotas. Existing local public-client bounds remain authoritative for this patch.

[Marino et al.](https://arxiv.org/abs/2602.14860) independently verified: graduation modeling conditions on SOL locked and launch structural/behavioral variables. Graduation prediction is not after-cost tradable return; detailed sample percentages in the Lead note were not independently reproduced this round. [Mongardini/Mei](https://arxiv.org/abs/2507.01963) studies 34,988 tokens and reports artificial-growth evidence for 82.8% of its >100% return subset. This is a selected-study finding, not a universal rug probability or an entry label for this project. Neither paper justifies buying a winner whitelist or treating current holder data as historical.

## Casebook and current coverage cutoff

matched_casebook_30_20260909.json contains 30 unique SURGE winners and 30 unique matched Tokens from existing token_precursor_cohorts.csv: ten pairs each BSC/Solana/Robinhood, same chain/UTC date/pool-age bin, 29 failure/crash and one ordinary match. Dates 2026-08-31 through 2026-09-03. Outcome labels never become entry features. Liquidity bin, exact minute and provider are not controlled; the existing artifact does not support a claim of fully matched tradable comparison. No new backtest or production scan was used to create it.

Current direct pattern pre-bridge baseline at 18:25:48Z: evaluation IDs1183010..1188853;2680 pattern rows/176 Tokens;33 Gecko-first qualified anchors,27 mature150s/6 censored;9 second same-source frames,0 dual60/120 checkpoints. This is current-window evidence, not a restatement of the older N19 source32 snapshot. See pre_bridge_pattern.json and reproducible pattern_coverage.py.

backup_retention_matrix.json adds read-only schema hashes, trade/snapshot/policy frontiers for five backups. Frontiers differ (trade359334..426959); no equivalence has been proven. Preserve all.


## Controlled bridge trial and protection rollback

Code cd579c8 passed targeted tests, including exact identity, unusable Dex, same-generation suppression, future-frame rejection, deadline, 429/backoff and held-start priority. It retained cap10/chain, base3/4/3, TTL, scheduler cadence and shared2.1s Gecko pacing. It adds marginal checkpoint requests within the shared rate budget; it does not promise unchanged total call count. No broad claim of request-rate compliance from provider documentation alone.

Trial process started around18:30Z, pre-frontier1189777. Health running; initial live API timed out once and later returned running. Four immutable registration/additions digest comparisons passed before S1 registration. Runtime bridge telemetry reached2 batches/3 requested pools/1 usable observed frame, one unusable response, checkpoint skips and shared cooldown skips. Watch capacities remained bounded. Process-local passive drops stayed0.

At18:36:34Z the strict post-pattern cohort had8 Gecko-first anchors, only5 mature150s, zero same-source second/dual checkpoints;3 censored. This is INSUFFICIENT_COVERAGE_EVIDENCE, not proof that Gecko exact pools cannot bridge. Existing watch occupancy, Dex timeout gating and source backoff remain competing explanations. No P0-C lease or S2 threshold introduced.

Protection triggered: baseline held_fetch p95=1.721708s; successive trial reads2.254086s then2.517842s exceeded the predeclared25% guard. Pattern p95 was7.42–7.56s (below15s), held apply p95~0.059s, drops0. Traffic/provider variation prevents attributing the regression uniquely to bridge; conservative reversal is required anyway. Existing original_pool source reported429 at18:36:21Z; bridge telemetry had no own429 and only two batches, so increased rate-limit causality is not established.

Revert commit6e3097c removes ONLY cd579c8 and was pushed. Paper restarted through existing launcher to load reverted code; web/funnel remained running. This is a scoped rollback, not periodic restart as a dormancy remedy. No funding/reset/Live/history changes. Next bridge proposal must first explain held latency and measured request-start occupancy; do not auto-reapply cd579c8 or resurrect surge23/25. S1 is independently registered and awaits natural paired outcomes.

## S4 passive components and final boundary

scripts/report_regime_shadow.py reads at most4000 existing evaluation IDs with causal three-clock checks and one latest valid frame per token. Outputs provider mix, early valid-activity share, median liquidity and turnover per chain; never reads outcomes or changes trading. First artifact regime_shadow.json at18:36:12Z has1953 frames and29 rejected frames. Watch-selected denominator is explicitly not chain-wide launch intensity or survival. No scalar ranking or sizing/entry selection deployed. Syntax validation and actual bounded production read passed.

Remaining: full linked feature/next-frame/terminal causal funnel; accepted source continuity; meaningful post-frontier coverage; external casebook details beyond the30 locally matched pairs; robust S1 terminal evidence. S2 requires working early trajectory coverage, S3 profitable paired evidence; neither gate is met. Storage deletion blocked by tool policy, not completed. This tranche is not represented as fully completed or as evidence of alpha.

Rollback acceptance18:38:59Z: health ok/runtime running, live running; evaluation frontier1191968, bridge telemetry key absent (reverted runtime loaded). Held_fetch p95=2.001924s, held_apply_exit p95=0.050279s, pattern p95=6.245846s, passive drops0. Short post-restart sample only; no causal performance-improvement claim. S1 positions still0. See rollback_acceptance.json.


## Evidence addendum34 — Lead updated ledger read

Source: C2C-20260909-AGE-RATE-PAIRED-EVIDENCE-34 and updated STRATEGY_FORWARD_CONVERGENCE_20260909.md section1. These newer rounded values are Lead-reported; this acknowledgment did not independently rerun SQLite. Exact cutoff was not supplied. Preserve earlier independent cutoff values as historical, not contradictory replacements.

97 completed Token+shadow_cohort matches: candidate/control each+183.973U, paired delta0. Completed control without candidate counterpart:208 positions/-242.877U. Candidate116 terminals/+172.285U; control305/-53.905U. The unmatched-control set uses a different counterpart condition from all unpaired terminal rows, so do not reconcile totals by subtraction without row-level definitions.

Decision: supports age normalization as a selection-quality gate, not improved common-trade execution/exit economics or proven alpha. Top3 BSC concentration remains a falsifier. S1 retains frozen same-entry/same-fill15/60-minute comparison; no threshold/funding/freeze change on this addendum alone. Require natural paired terminal deltas, chain/date and top-winner-removal evidence. No runtime/SQLite writes.


## Addendum36 integration — completed descriptive research, remaining causal work

Read RIGHTTAIL_CASEBOOK_RECOMPUTE_20260909.md. Lead-reported recomputation frontier: snapshot1996109 at2026-09-08T18:37:30.305955Z; trade510712 at18:37:22.717090Z. Codex did not duplicate this computation or independently certify the underlying rows in this integration.

Accepted as attributed descriptive findings:14/16 qualifying local price/liquidity anchors;12/14 have observed6h doubling. No-BUY, late-BUY and early-BUY/later-wave patterns require different mechanisms. Preserve HOT_IMPULSE / QUIET_ACCELERATION / REAWAKENING as separate falsifiable hypotheses sharing a possible age-normalized quality filter; no universal first-frame heat/count gate follows from selected winners. A zero aggregate is not proof of zero real trading.

Important limitations: report defines MFE from same-token snapshots, not an explicitly frozen exact-pool/upstream, three-clock, strict-next, costed execution path. Its16-case descriptive reconstruction/ledger attribution must be reused, but does not complete the remaining strict-forward reconstruction. Its83,859 historical60m observations include winners and losers; they are not83,859 negative tokens. Older all-Dex dates are not same-date/provider/age matched controls for these16. Missing-anchor cases remain data-unknown, not strategy failures. External-source claims in the Lead report were not independently reverified in this ACK.

Current implementation supersedes stale report lines: S1 registered18:35:13Z, not merely implemented. Bridge trial was subsequently reverted6e3097c after held-latency protection; no automatic redeploy. Age-rate updated34 figures supersede older numerical cutoff only, preserving provenance. Keep fixed40/50 underperformance and broad automatic hard-stop re-entry rejection. No new router/threshold/account introduced.

Next nonduplicate research input is the existing row-level query/frame artifact for this recomputation, if available; report itself supplies no exact path to it. Reuse it to resolve pool/source transitions, causal fill eligibility and same-age/date ordinary/failed controls rather than rerun the descriptive table. Source continuity repair and held-priority acceptance remain prerequisites for QUIET_ACCELERATION. Sixteen-case scope remains ACTIVE until these gaps are resolved.
