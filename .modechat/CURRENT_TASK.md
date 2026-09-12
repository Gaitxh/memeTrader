# Authoritative current checkpoint

```json
{
  "cycle_id": "round-120-18-activity-floor-and-artifact-disproof",
  "workspace": "H:\\OpenTrader\\memeTrader_2",
  "runtime": {
    "db": "data/memetrader_forward.sqlite3",
    "epoch": "chain-meme-trader/funding-20260906-v002-final-1000",
    "supervisor": "scheduled task 'memeTrader Paper Bot' -> scripts/run_paper.ps1 (auto-restarts the trader 5s after it exits)",
    "web": "http://127.0.0.1:8790 (chain-web, separate process)",
    "restarted": "2026-09-12T21:19:08Z (round 120-17; registers exit150_full15_v1 + exit150_full25_v1 at frontier 32175)",
    "process_note": "each service shows TWO python processes - the .venv parent and a system-python RE-EXEC'd child. This is by design, NOT a duplicate-writer hazard."
  },
  "ROUND_18_FALSIFIED_entry_features_cannot_predict_the_15pct_touch": {
    "status": "FALSIFIED before building. Do NOT build a '+15%-touch predictor' / 'quiet pool' entry filter.",
    "why": "Position level looked strong (mcap ratio 0.18, sells 0.00, both 'separated'), but every check kills it: (1) positions are projected from a cohort=(token,snapshot) x many arms, so they SHARE one feature vector and per-token medians are literally identical (bsc:0x1853979987 mcap 27,377/27,377, trades 11/11) - the within-token test had no variance by construction; (2) at the correct unit (167 cohorts, 7.3/token) the within-token rank correlation is 0.000 for EVERY feature (liq and mcap: 10 tokens negative, 0 positive); (3) the direction INVERTS when the 5 luckiest tokens are removed (trades 0.12 -> 1.22, sells 0.09 -> 2.04, mcap ratio -> 1.00); (4) token-clustered bootstrap CI [-0.127, +0.297] spans zero; (5) economically backwards - quiet pools -12.57U/pos vs busy -4.25U/pos."
  },
  "ROUND_18_FOUND_one_filterable_population_is_69pct_of_the_loss": {
    "headline": "An activity floor on the entry snapshot's OWN fields collapses the death rate. Write-off rate 34.8% -> 6.0% at trades>=30 (vol5>=10000 -> 8.4%). Token-clustered bootstrap on the per-position gain: +9.73 U/pos, 95% CI [+3.93, +14.17], EXCLUDES ZERO.",
    "chain_stratified_mechanism": {
      "bsc_lt30_trades": "404 positions, 78.6% write-off, -15.39 U/pos  <- -6,218U = 69.2% of the entire -8,990U epoch loss",
      "bsc_ge30_trades": "132 positions, 7.6% write-off, -4.75 U/pos",
      "solana_lt30_trades": "55 positions, 0.0% write-off, -2.67 U/pos",
      "solana_ge30_trades": "352 positions, 6.8% write-off, -4.43 U/pos",
      "baselines": "bsc 547 pos / 61.4% wo / -12.82 U/pos; solana 407 / 5.9% / -4.19; robinhood 93 / 0.0% / -2.97"
    },
    "near_miss_correction": "It is tempting to read 'the floor hurts Solana because kept -4.43 is worse than dropped -2.67'. That is the WRONG comparison. Removing a set that loses -2.67U/pos IMPROVES the book by +147U. The floor helps BOTH chains: +6,394U on BSC, +148U on Solana.",
    "units": "the gate's own quantity is `trades = last['buys'] + last['sells']` and `last['volume']` - the SAME 5m fields measured here."
  },
  "ROUND_18_COMBINED_levers": {
    "actual": "-8,990.05U over 1,041 positions (-8.64 U/pos)",
    "tp_only": "-3,743.41U",
    "floor_only_trades30": "-2,462.54U over 575",
    "floor_plus_tp": "-2,162.84U over 575",
    "best_vol5_50k_plus_tp": "-506.00U over 275 (-1.84 U/pos)",
    "verdict": "The two levers PARTIALLY OVERLAP rather than add (5,247 + 6,528 != 6,827) because the floor removes positions the take-profit would have rescued. Best case is a 94.4% loss reduction but token-clustered bootstrap gives 95% CI [-1,429, +141] and P(profitable)=12.9%. IT STILL LOSES, and the residue is concentrated (1 of 7 traded tokens is -250U)."
  },
  "ROUND_18_ROOT_CAUSE_why_the_existing_defence_never_bites": "The system ALREADY has 296 numeric entry gates, consumed at revision_evidence_extensions.py:279, with min_trades 4-12 and min_volume 300-1200. The transition is between 10->20 trades and 1,000->3,000 volume, so THE EXISTING FLOORS ARE CALIBRATED EXACTLY WHERE THEY DO NOTHING (trades>=10 is worth +552U of a possible +6,528U). Structurally: those floors live on evidence_extension_l0 arms that hold 1-2 positions each, while the 1,409 positions actually held come from 154 isolated_cohort_observer arms whose ENTIRE entry_filter is {direction, max_concurrent_positions: 2, single_token_lifetime_entry: True} - no activity gate at all.",
  "ROUND_18_HOOK_LOCATED_not_landed": "store.py:27832-27850 is the cohort acceptance loop; each qualifying policy commits at accepted_cohort_signals[arm]=signal (27850). A new arm can be screened there by its own id (existing arms -> allow immediately), precedent being store.py:27951 which dispatches an arm to its own module via entry_filter['failed_impulse_cooling']. NOT LANDED because a new cohort arm only trades if the cohort evaluator emits a signal for it: cohort_signals is an INPUT parameter (store.py:27508) produced upstream, cohort_experiment_policies() enumerates its arms explicitly, and the alpha149 cohort arms emit via alpha149.signals_for from SPECS. So the additive path is: append a new arm to alpha149.SPECS (the established wave pattern) + the one-line screen + its own register_* frontier. NEEDS VERIFICATION that the new arm reaches cohort_signals before it is trusted.",
  "ROUND_18_FUNNEL_REASONS": "evaluations this epoch: cohort_observation 11,667 | no_active_matching_entry_policy 9,166 | pattern_observation 7,555 | entry_pool_liquidity_absent_curve_stage 2,714 | invalid_exact_asof_market_snapshot 1,807 | entry_pool_liquidity_below_configured_floor 1,055 | entry_pool_liquidity_unknown 396 | entry_snapshot_too_old 12.",
  "ROUND_18_JOIN_KEYS_measured": "shadow_cohort_id -> v6_cohorts.id 1098/1098; source_entry_fill_id -> v6_entry_fills.id 1091/1098; entry_snapshot_id -> token_snapshots.id 1091/1098; entry_fill_id -> v6_entry_fills.id 0/1098 (silently empty - the trap that bit a previous round). Rich per-arm feature vectors are NO LONGER usable historically because round 120-9 compacted them to 3 fields.",

  "ROUND_17_EXIT_SIDE_IS_CLOSED": {
    "status": "Four independent falsifications on real forward marks (906 closed positions, 24 tokens, actual -7,962.84U). No exit rule, level or cadence change can recover the loss. ALL remaining effort belongs on the ENTRY side.",
    "1_no_tighter_stop_helps": "Enforcing -0.15/-0.20/-0.25/-0.30/-0.40/-0.50/-0.65 econ on EVERY position gives -358/-149/-89/-113/-149/-152/-142 U versus doing nothing. Tightening also stops the positions that recover.",
    "2_stop_fires_correctly": "mark[-2] median econ -12.4% -> mark[-1] -36.0%, a median 23.6% single-step drop. Inter-mark gap 10.9s (config TARGET_SECONDS=15) and the last mark is 1-3s before close, so we were neither starved nor blind. The overshoot is a gap-through INSIDE one interval - there is no delay to remove.",
    "3_no_liquidity_warning": "0s median warning at every liquidity threshold 1k..12k. NOTE: I suspected a 50,000 liquidity clamp and FALSIFIED it as my own aggregation artifact (11,750 marks, 2,969 distinct values, max 67.5M; liquidity+volume co-move 1,507 times vs liquidity-alone 29; 0 pools show price-moving-but-liquidity-frozen). Do not re-investigate.",
    "4_lease_contention_not_the_cause": "observation_leases145.replaceable_early admits only bucket=='early' leases (growth/mature are not evictable - a real asymmetry) BUT marks already beat the 15s target, so it is not this round's bottleneck."
  },
  "ROUND_17_PROFIT_CAPTURE_FINDING": {
    "headline": "The user's problem '金狗拿不住' is BACKWARDS. Only 5 of 906 positions ever reached +100% econ, but 241 touched +15% and 186 of those finished NEGATIVE (only 55 positive). Their realised total was -3,059.50U; banking the whole position at +15% would have returned +723.00U. The failure is NEVER TAKING PROFIT, not failing to hold.",
    "priced_on_the_same_replay": {
      "full15_100pct_at_15": "+4,178.36U",
      "full25_100pct_at_25": "+2,796.84U",
      "full10_100pct_at_10": "+4,107.39U",
      "bank15_50_40_50_DEPLOYED": "+2,446.19U - captures only 58.5% of the effect",
      "bank25_50_40_50_DEPLOYED": "+1,498.52U"
    },
    "the_50pct_left_riding_is_what_round_trips": "full15 is worth +1,732U more than the deployed bank15. The LEVEL is not knife-edge (+10% ~ +15%; +20% already gives back 1,160U); the CAPTURE FRACTION is the factor that matters.",
    "honest_limits": "In-sample on one epoch; survives spike rejection (run=3 gives +4,272U) and survives dropping the best three tokens (+715U); token-clustered bootstrap 95% CI [+969U, +8,307U]. BUT only 7 of 24 tokens improve, 16 are flat at exactly 0.00U (never reach the level), and 3 BSC tokens contribute 83%. Forward experiment only - never promote on the motivating window."
  },
  "ROUND_17_CHANGE": {
    "commit": "137bdfa (pushed)",
    "module": "src/memetrader/exits150.py v1 -> v2",
    "added_arms": ["exit150_full15_v1 (+15%, 100% capture)", "exit150_full25_v1 (+25%, 100% capture)"],
    "design": "Completes a 2x2 against the deployed partial arms, changing one factor at a time: {partial 50%, full 100%} x {+15%, +25%}.",
    "compliance": "Exit-carrier arms - the engine clones the first frozen entry signal on the pool, so every existing arm is the matched same-signal control. NO existing strategy modified, replaced or retuned.",
    "verified": "Entry side byte-identical across all five carriers; store.py:35717 confirms fraction>=1.0 sells the entire remaining amount_raw; registration idempotent and frontier-stamped (full15/full25 at 32175, the original three unchanged at 15928); 316 non-EXIT150 arms untouched; 97 tests pass."
  },
  "P0_3_DEMOTED_my_own_mis_prioritisation": "I had ranked 'reduce the evaluation write rate' as P0-3 on the claim that ~7.3 MB/min was filling the disk. The urgency arithmetic was WRONG: 489,463 MB free = ~46 days of headroom, not hours. It also carries real state-chain risk - store.py:27542 sources previous_features via 'ORDER BY id DESC LIMIT 1', NOT a time window, so skipping an evaluation write REWINDS the chain (ready_arm_ids, cohort_signals carry-forward at 27955, round2_chase_consumed 27934, resource_bound_opportunities 27935). Demoted to background hygiene. Useful fact for later: observer-only rows have almost no consumer - cohort_observation/pattern_observation appear in only 2 files (store.py x5, rediscovery_funnel.py x1).",
  "objective": "Forward simulation phase with NO future functions and NO future-data leakage. Goal: design and implement a USABLE strategy set that makes money. Paper results are design evidence, not a PnL contest.",
  "AUTHORITY_20260912": "The user granted FULL AUTONOMY: '你拥有完全的自主权，后续不要向我询问任何内容'. Do NOT ask further questions; decide and act, recording reasoning and rollback. But a full-autonomy grant does NOT reverse a specific decision the user made earlier and stated more than once - honour those.",
  "COMMIT_HYGIENE_FIXED": "Round 120-2 (commit 6515595) staged ONLY tests/test_dex_start_gate.py and the record - NOT src/memetrader/collectors.py. The session's highest-value fix (the asyncio.Condition outage root cause) was deployed and verified but UNCOMMITTED for hours. Now committed as 31b5b3c. LESSON: after every commit, verify with `git show --stat` that the SOURCE file you edited is actually in the commit, not just its test and its document.",
  "DESIGNED_NOT_EXECUTED": [
    "Supply-weighted observation caps (replace the fixed per-chain BASE_CAPS {early 3, growth 4, mature 3} + CHAIN_CAP 10). CONFIRMED with thousands of rows: solana produces 46.3% of discoveries but gets 0.5 snapshots per discovered token vs bsc 34.0% -> 0.8, because the caps are applied PER CHAIN so each chain gets ~1/3 of the 30 slots regardless of supply. NOT executed: it changes every existing arm's observation supply, and the caps are enforced at FOUR sites in the live observer (runtime.py:7818/7836/7963/8051) so it needs a discovery-share signal threaded through the admission path - not safe to land in a partial round. Outcome side is thin (BSC 66.7% dead vs Solana 0.0% but only 18 tokens ever traded, 6 written off here); the old device pooled gives BSC 216/686 write-offs vs Solana 0/1599.",
    "cohort_signals payload reduction. cohort_observation rows are 582.2 MB of a 920.7 MB DB (63%), avg 86,101 B, max 444,925 B. Inside one 98 KB row cohort_signals is 81,188 B (83%) holding 16 entries at ~7,780 B each carrying the SAME decision_evidence.feature_vector (one vector copied 16x); outcomes has 185 entries with only 3 distinct blocker values (grouped: 135 B vs 13,381 B). A lossless redesign removes ~85-90% of 63% of the DB and the same share of write rate. NOT executed because cohort_signals is NOT telemetry: it is read live by store.py:28919 (entry projection), store.py:34208 (exit path), store.py:27887/27942/28046 (cohort episode continuity), cohort_enrollment.py:67, narrative_hold.py:258, mode_learning145.py:234. Needs a reader migration and its own round. DB growth measured at ~7 MB per 10 min = ~1 GB/day, so this is an active operational concern."
  ],
  "COVERAGE_BOTTLENECK_IS_LOCATED": "The token-level signal rate of 0.38% comes from WATCH CAPACITY - how many pools can be observed densely - NOT from a continuity, freshness or mechanism-threshold defect. The system observes the pools it selects extremely well (gap p50 1.4-2.7s, 96-99% of gaps under 30s, and 4 of 6 busiest pools PASS the 30s-window test with the two failures marginal) and everything else about once. 30 observation-lease slots (3 chains x {early 3, growth 4, mature 3}, TARGET_SECONDS=15) plus a 24-slot mover registry, currently at capacity (watched=34, mover_watching=24). Mechanisms fire amply: deep_pool_flow 370 ready, nonbsc_flow 250, mid_band_flow 227, righttail_lottery 538.",
  "DO_NOT_BUILD": [
    "A cadence-aware engine on a larger MAX_GAP_SECONDS - it would unlock nothing, and widening only the gap cannot help because the window's 40-SECOND SPAN is what binds. Changing the span changes what return_fraction / acceleration / volatility MEAN, so it would need NEW mechanism kinds calibrated on the new features, not new arms on the old ones.",
    "An observation-depth-budget reallocation - already 54.2% of mover slots are in the good bands (20k-100k: 6, >=100k: 7) and 1k-5k holds only 12.5%.",
    "A mark-supply fix - 1706 mark_history rows per 15 min here versus the old session's 46; 494 of 518 positions received more than one in-window mark.",
    "Loosening the engine's 30s freshness rule - only 1 of 6137 snapshots exceeds 30s and the engine refusal ratio is 12.2%."
  ],
  "next_action": "P0-NEW land the ACTIVITY-FLOOR entry arm - it is the single biggest lever found (404 low-activity BSC positions = 69.2% of the epoch loss; write-off 34.8%->6.0%; +9.73U/pos with token-clustered CI [+3.93,+14.17]). Path: append a new arm to alpha149.SPECS (the established additive wave pattern) + a one-line screen at store.py:27850 keyed on its own id + its own register_* frontier. FIRST verify the new arm actually reaches cohort_signals (store.py:27508 is an INPUT parameter; cohort_experiment_policies() enumerates arms explicitly; alpha149 cohort arms emit via alpha149.signals_for from SPECS) - do NOT trust an entry arm that silently never fires. Levels from the write-off collapse, not the in-sample PnL sweep: trades >= 30 and/or vol5 >= 5000, applied globally (it helps BSC +6,394U and Solana +148U). See ROUND_18_HOOK_LOCATED_not_landed and ROUND_18_ROOT_CAUSE_why_the_existing_defence_never_bites. P0-1 settle exit150_full15_v1 / exit150_full25_v1 to >=20 per side and test the CAPTURE-FRACTION hypothesis forward. P0-2 re-run scripts/paired_arm_ab.py as settled counts grow; when alpha149_merged_multi_setup_v1 reaches >=20 paired cohorts add it to the pause list. P1 explain the -506U residue (1 of 7 traded tokens is -250U). DO NOT build a '+15%-touch predictor' or 'quiet pool' filter - falsified in ROUND_18_FALSIFIED. P0-3 (write rate) stays background - 46 days headroom, carries state-chain risk.",
  "MEASUREMENT_DISCIPLINE": "Four hypotheses have been killed by measurement across rounds 120-5/120-6 and ONE WAS A BUG IN MY OWN PROBE ('0 of 18 pools can form a window' - the query filtered provider LIKE 'dexscreener%', excluding the strategy-observer mirror rows). None produced a code change; all would have looked like reasonable fixes. ALWAYS take a second independent measure before publishing a '0 samples / stalled / defect' claim or changing code. Also: never LIKE wildcards on arm_id; use julianday() not datetime('now'); dedupe snapshots by (token_id, observed_at); separate windowed from all-time totals.",
  "authoritative_current_numbers_20260912T2027Z": {
    "source": "scripts/supervise_metrics.py --hours 2 AND scripts/trade_context_ledger.py --minutes 180",
    "discovery_per_hour": 3523.7,
    "evaluations_sampled": 17427,
    "admitted": 592,
    "positions": "450 total, 398 settled, 177 write-offs, WIN RATE 8.5%, total -4091.68U, PF 0.03",
    "positions_per_token": 12.75,
    "TOKEN_SIGNAL_RATE": "0.38% (10 of 2641 evaluated tokens reached any arm) - the user's core complaint, precisely located, long-standing (old session baseline 0.57%)",
    "WASHED_OUT": "0 (0.0%) - no position ran >=+50% then closed at a loss, so 'cannot hold a winner' is NOT supported by this device's evidence; the money is lost on never selecting a winner plus friction",
    "only_positive_exit_types": "market_mark_trailing_exit 9 closes +43.06U; alpha149_plateau_stall 5 closes +9.24U",
    "hold_bucket_worst": "5-15m: 215 settled, 7.0% win, -3232.86U (almost all of it the 177 write-offs)",
    "hard_stop_24h": "114 closes, -502.44U, mean -4.407U",
    "unresolved_error_cases": 15
  },
  "cross_session_scripts_that_ALREADY_EXIST": [
    "scripts/supervise_metrics.py - funnel/coverage/economics/capacity/stability + 9 review triggers, writes data/reports/supervise/",
    "scripts/trade_context_ledger.py - per-trade context: discovery source, entry mechanism, MFE, exit reason, hold minutes, washed_out flag",
    "scripts/paired_arm_ab.py - within-cohort paired A/B, token-clustered bootstrap CI, MIN_SETTLED_PER_SIDE=20, prints NOT READY below that",
    "scripts/register_alpha149.py - idempotent append-only arm registration"
  ],
  "confirmed_facts": [
    "Round 120-3 committed and pushed as c493589 (120-2 was 6515595, 120 was 74ea78e) on branch work/2026-09-04-c2c-115000-additive-strategy.",
    "EXIT150 IS LIVE: three exit-carrier arms registered at a TRUE forward frontier (activation_snapshot_id 15928, not the legacy 0), 316 -> 319 policy additions, present in the running manifest (446 policies), and already holding positions.",
    "The carrier contract already existed: alpha149's signal loop emits entries from SPECS only and then clones the first firing entry arm's signal into every EXIT_ARMS entry. So each new arm gets the SAME opportunity as whichever entry arm fired first and only its exit differs - every existing arm is the matched same-signal control. No existing strategy was modified.",
    "THE MONEY DEFECT: per-position peak economic return was p50 +22.7% / p90 +34.8% / max +55.0% (+20% reached by 51.0%, +30% by 32.0%, +60% by 0.0%) while the configured first take-profit tier is +80%. next_tp_index and principal_recovered were 0 on ALL 350 positions - the ladder fired zero times and no profit was ever banked (give-back 4508.94 USD).",
    "The stop sat inside the noise: hard_stop_return -0.20 = a -13.3% price move vs the pools' own p90 30-second move of 9.49%; 44 of 92 hard stops fired within one minute; hard_stop_liquidity_veto_usd was set on 0 of 92 arms.",
    "The three arms vary exactly one thing each: bank15 vs bank25 isolates where to take the first profit; bank15 vs widestop isolates stop width. Each leaves a ~15% moonbag under the trailing stop.",
    "Existing arms provably untouched: alpha149_vol_scaled_exit_v1 d7b2084ffe293867, alpha149_merged_multi_setup_v1 3029187564e9c2f1, alpha149_confirmed_stop_steady_v2 20460e412abb69a2, all take_profit=[] and the same stops as before.",
    "OUTAGE ROOT CAUSE (round 120-2, fixed): collectors.py wrapped condition.wait() in asyncio.wait_for; the timeout cancels the inner wait(), leaving the asyncio.Condition lock released, after which notify_all() raises and the Condition is permanently unusable. Both per-host start gates now pace outside the condition.",
    "THE CONCENTRATION CAP WORKS: fan-out per cohort fell from 35-42 arms to 0-4 and the worst burst from 40 positions in one second to 4; a live pool sits at exactly 8 arms (the cap). Distinct tokens rose 11 -> 13 -> 15 as arms spread to other instruments.",
    "LOOK-AHEAD AUDIT CLEAN (round 120-2): 0 of 14,040 evaluations consume a snapshot observed/ingested/recorded after the decision; 0 of 4,468 rows have a feature timestamped after their own decision; all four ordering invariants hold. The 12 initial flags were a false positive - the running high is seeded with the entry price at open.",
    "The 169 write-offs are 4 real data reads on 4 BSC pools that are genuinely dead (independently re-verified live). The write-off arithmetic books exactly -20.00 and is correct; do not re-open this.",
    "Cash exhaustion is REFUTED: 443/443 arms can open a 20 USDC position (min arm cash 880). shared_available_cash_usd=0.0 is min() of an empty dict.",
    "489718 arm-instances block at await_distinct_dex_trajectory_frame; only 321 of 954 accepted frames (33.6%) yield a usable 30s window because the real cadence is 60-120s.",
    "tests/test_cohort_store.py fails, but it ALREADY fails at pristine HEAD (verified in a separate git worktree of 74ea78e): runtime.py:7763 assumes get_kv never returns None, and a kv value of JSON null breaks it. Pre-existing, not ours."
  ],
  "implemented_this_round": [
    "src/memetrader/exits150.py - three exit-carrier arms with reachable staged ladders (bank15 / bank25 / widestop), paper_only, notional 1.0.",
    "alpha149.py wave 42: additive import merging exits150 into OVERRIDES/EXIT_ARMS; deliberately NOT into SPECS.",
    "store.py register_chain_meme_exit150_experiments() cloning this epoch's own registered exit carrier as the schema template; called from runtime.py's registration block.",
    "tests/test_exit150.py (11 tests); 85 tests pass overall. test_alpha149's blanket 'every EXIT_ARMS entry has trajectory_exit' assertion replaced by the stronger real invariant: every exit arm declares exactly ONE exit mechanism."
  ],
  "open_risks": [
    "src/memetrader/store.py, runtime.py, collectors.py and alpha149.py each carry this round's changes AND pre-existing uncommitted changes from earlier rounds; only new files and records were staged. Staging those four is still pending.",
    "EXIT150's ladder CHOICE is in-sample on one 87-minute window. It must be judged only on data observed after frontier 15928 and must not be promoted on the strength of the window that motivated it.",
    "max_concurrent_positions registered as 2 (inherited from the live carrier template), not the 4 declared in the module. The append-only ledger cannot be updated and 2 is the more conservative bound; recorded so it is not mistaken for a bug.",
    "token_discovery_quote_attempts and source_poll_attempts are 0 rows, so the DexScreener failure mode is inference from a traceback, not proof.",
    "pretrade_rug_safety_registrations covers Solana only and produced 0 assessments.",
    "5 pump_native_absorption_fast_v1 positions bypass the cohort/decision/fill contract (entry_snapshot_id NULL, stake ~4.71) while landing in the same positions table."
  ],
  "rules": [
    "Live stays locked; Paper only; no reset or re-initialization; new strategies join only at their own deployment frontier.",
    "Do not modify or replace existing strategies; improvements arrive as NEW additional strategy modules.",
    "Never loosen strict timing, identity, protocol-validity, account-truth or dead-surface rules to create trades.",
    "Every optimization must be gradual and reversible, and must not break stability, realtime behaviour or accuracy."
  ]
}
```

Only this revision defines current work. Historical rounds are audit evidence, not an active queue.
