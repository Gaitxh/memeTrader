# Authoritative current checkpoint

```json
{
  "cycle_id": "round-120-30-undensed-lead-closed-diagnosis-complete",
  "ROUND_30_DENSE_EPISODE_FREE_LEAD_CLOSED": {
    "the_lead": "Round 29 flagged the 11 entered tokens with no >=3-frame episode as the most promising remaining lead, BECAUSE widening it would need no observation budget.",
    "IT_DOES_NOT_SURVIVE_CONTACT": "All 11 are the native_protocol_model lane - 100%. 11 tokens, all solana:...pump, exactly 1 POSITION EACH, realised -10.8U over 11 positions (-0.98U/pos). Closes: 9 hard_stop (-12.83U), 1 trailing (+2.64U), 1 max_hold (-0.40U). By contrast the 37 dense-episode tokens are isolated_cohort_observer 2,485 (98.7%) + isolated_pattern_observer 33.",
    "why": "Their token-level observation is near-zero (0-4 snapshots each, 0-1 observer frames), so these tokens are not 'undensed' - they are TRADED ON AN ENTIRELY DIFFERENT EVIDENCE BASIS. Not a coverage route widenable within the DEX-pool observation architecture; a separate protocol lane with one position per token and no demonstrated edge.",
    "round_29_caveat_resolved": "Dense observation is the route for 37 of 48 entered tokens (77%); the other 23% arrive through a lane that is neither free to widen nor profitable on the evidence so far."
  },
  "ROUND_30_ANALYTICAL_HAZARD_native_lane_is_a_join_dead_zone": {
    "the_observation": "All 11 native-lane positions carry entry_snapshot_id = 0 (NULL or dangling) with entry_reason = later_observed_protocol_model_paper. The cohort lane by contrast is CLEAN: 2,485 positions, 0 NULL, 0 dangling.",
    "NOT_a_defect": "later_observed_protocol_model_paper names next-observed / trigger-anchored execution explicitly, which is the documented and frozen semantic. The position is valued on the NEXT observation rather than an as-of entry snapshot. Do not report this as missing evidence.",
    "but_IT_IS_an_analytical_dead_zone": "These positions CANNOT be joined to entry-time market features at all. Any query joining positions to token_snapshots on entry_snapshot_id SILENTLY DROPS THEM - a 0-row result that looks like 'no data' rather than 'different lane'. This is the same trap that bit an earlier round. STANDING NOTE: for any entry-feature query, STATE WHICH LANE IT COVERS."
  },
  "ROUND_30_DIAGNOSIS_IS_COMPLETE": {
    "every_link_measured_and_every_candidate_eliminated": "discovery healthy; collection healthy (94.5% observed); feature/trajectory healthy (66.8% form ready 30s windows); processing speed NOT binding (p50 0.18s observed->position); freshness rules NOT binding (0.03% of evaluations); signal generation NOT binding; arm fleet not redundant (311 contracts) and not prunable (r25); token-level exclusion unvalidatable at n~40 (r26); capital/concurrency/pending intents NOT binding (1.35% utilised, r28); slot turnover not a lever (r29); the dense-episode-free lane not widenable and no edge (r30).",
    "THE_ANSWER_TO_THE_OBJECTIVES_CORE_QUESTION": "No threshold, logic rule, risk rule or processing limit is systematically blocking tradeable candidates. Dense observation converts at 7.02% (37 of 527) against 0.39% overall - an 18x difference - so the system is not failing to convert what it can see, it is failing to GIVE CANDIDATES ENOUGH OBSERVATION TO BE JUDGED. THE BINDING CONSTRAINT IS DENSE-OBSERVATION COVERAGE: 4.4% of observed tokens (527 of 11,991).",
    "what_remains_honestly": "The binding constraint is NOT mine to change - it is a user-decided budget item (increase declined round 79; partial increases approved rounds 83 and 88) and the completed evidence base is now the deliverable on that point. Six forward experiments are in flight and NONE is readable yet; exit150_full15_v1 is closest at 17 of 20 settled and positive per position. Their verdicts need WALL-CLOCK TIME, not more analysis. Everything else in my authority was either shipped or closed by measurement."
  },

  "ROUND_29_SLOT_TURNOVER_CLOSED_AS_A_LEVER": {
    "the_candidate": "replaceable_early evicts only bucket=='early' leases, so growth/mature leases squat their full PHASE_LEASE_SECONDS=300; with ~30 slots the ceiling is ~30 x 3600/300 = 360 dense pools/hour. The premise was that a 300s slot is mostly idle after the interesting frames arrive.",
    "THE_PREMISE_IS_FALSE_measured": "7,964 reconstructed observation episodes (observer snapshots, same token, gaps <=60s): only 863 (10.8%) reach >=3 frames; 6,184 (77.6%) are a SINGLE frame; median duration 0.0s. Time to the 3rd frame among those that reach it: p25 29.2s, P50 31.6s, p75 52.0s, p90 65.1s - a window forms by ~32s median and ~65s at p90, comfortably INSIDE the 120s early lease. So lease duration is NOT what prevents window formation.",
    "late_frames_are_not_dead": "New-information rate (price AND volume AND liquidity all changed) by elapsed time: 0-30s 11.1%, 30-60s 26.1%, 60-120s 24.0%, 120-300s 17.4%, 300-600s 16.8%, 600s+ 19.2%. After the first 30s the rate is FLAT at ~17-26% across every band and 2,359 new-information frames arrive after 300s. EARLIER RELEASE IS NOT FREE.",
    "bonus": "the 0-30s band is the POOREST at 11.1% - the round-21 over-polling signal, already addressed by round 22's adaptive cadence.",
    "verdict": "Slot turnover is CLOSED as a lever - the third no-budget candidate eliminated by measurement, after capital/concurrency (r28) and arm-fleet + token-exclusion (r25-26)."
  },
  "ROUND_29_BOTTLENECK_STATED_PRECISELY": {
    "the_numbers": "11,991 tokens observed; only 527 (4.4%) ever receive a >=3-frame episode - the minimum needed to be judged at all. Conversion: ALL observed 47/11,991 = 0.39%; DENSELY observed 37/527 = 7.02%. DENSE OBSERVATION CONVERTS AT 18x THE OVERALL RATE.",
    "the_statement": "The system is NOT failing to convert candidates it can see - it is failing to GIVE CANDIDATES ENOUGH OBSERVATION TO BE JUDGED. 95.6% of observed tokens never get a third frame, and 77.6% of observation episodes are a single sample that can never form a window.",
    "caveat_bounding_the_claim": "11 of the 48 entered tokens NEVER had a >=3-frame episode, so dense observation is the dominant route (77% of entries) but not the only one. A different lane reaches entries without it.",
    "ANSWER_TO_THE_OBJECTIVES_CORE_QUESTION": "The objective asks which link systematically blocks tradeable candidates through over-strict thresholds, logic or risk rules. The measured answer is NONE OF THEM. Over 28 rounds every threshold, risk rule, capital limit, concurrency cap, throttle, processing limit, arm-fleet property and token-selection rule has been tested and eliminated. The single binding constraint is DENSE-OBSERVATION COVERAGE - 4.4% of observed tokens. It remains a USER-DECIDED budget item (increase declined round 79; partial increases approved rounds 83 and 88) and was NOT changed."
  },

  "ROUND_28_CAPITAL_CONCURRENCY_HYPOTHESIS_CLOSED": {
    "the_last_unexamined_hypothesis": "That the account is out of usable capital, or concurrency / per-arm risk limits are saturated, so a fired signal cannot become a position. IT IS NOT - measured.",
    "measurements": "capital_eligibility = per_strategy_account_independent; starting_cash_usd_each_arm = 1000.0; 325 registered arms -> nominal capacity 325,000U; deployed in open positions 4,400.00U (220 positions) = 1.35% UTILISED; idle 320,600U; an arm at 1000U / 20U could hold 50 positions concurrently and the OBSERVED MAX is 8; max_open_positions = 0 (unlimited).",
    "no_capital_refusal_exists": "The entry-evaluation distribution has exactly 8 distinct reasons and NONE is capital-, cash-, limit- or concurrency-flavoured.",
    "global_throttle_is_empty": "max_pending_buy_intents = 8 is a GLOBAL cap that could have throttled a burst of buyers - there is no evidence it ever has: chain_meme_trader_order_intents 0 rows, execution_attempts 0, execution_results 0, quote_attempts 0, and marks with status=PENDING 0.",
    "useful_side_number": "468 fills across 37 DISTINCT TOKENS spawning 2,506 positions = 5.36 positions per fill. The cohort replication of round 25 seen from the execution side, confirming token breadth is set upstream at the signal/observation layer, not at execution. Trades: BUY 2,506 / SELL 1,600 / WRITEOFF 764."
  },
  "ROUND_28_CONSOLIDATED_BOTTLENECK_STATEMENT": {
    "every_link_measured": "discovery healthy (10,089 tokens); collection healthy (94.5% observed); feature/trajectory healthy (66.8% of accepted observations form a ready 30s window); processing speed NOT binding (observed snapshot -> position p50 0.18s); freshness rules NOT binding (entry_snapshot_too_old is 0.03% of evaluations, limit 90s); signal generation NOT binding; arm fleet not redundant and not prunable (r25); capital NOT binding (1.35% utilised); concurrency NOT binding (8 of 50); pending-intent throttle NOT binding (all queues empty).",
    "THE_SINGLE_BINDING_CONSTRAINT": "How many pools can be observed densely at once (~30 slots). Everything downstream - token breadth (46 tokens), effective sample size (~30), and therefore the ability to learn token selection at all - follows from that one number. It is a USER-DECIDED budget item (increase declined round 79; partial increases approved rounds 83 and 88) so it must NOT be changed silently. This round's contribution is that every alternative explanation is now eliminated by MEASUREMENT rather than assumed away."
  },

  "ROUND_27_METRIC_CORRECTION_writeoff_rate_is_not_a_loss_rate": {
    "the_claim_I_audited": "Since round 17 I have repeated 'exit150_full15_v1 has a 5.9% write-off rate against exit150_bank15_v1's 50.0%'. bank15 sells 50% at +15% and rides the rest, so a position can BANK PROFIT and still be marked written_off when the remainder's pool dies - which would conflate 'the pool died' with 'the pool died AFTER banking'.",
    "audit_result_safe_in_aggregate": "Across all 764 written-off positions: full loss (|pnl| >= 98% of stake) 97.4%; partial loss (banked something) 1.6%; positive PnL but marked written_off 1.0%. So in AGGREGATE written_off really does mean 'lost essentially everything' and the metric is safe for the fleet.",
    "but_UNSAFE_for_partial_exit_arms": "exit150_full15_v1: 1 wo (1 full-loss, 0 partial), realised +0.26U/pos. exit150_bank15_v1: 11 wo = 3 FULL-LOSS (-60.00U) + 8 PARTIAL (-28.87U, mean -3.61U), realised -6.01U/pos. exit150_widestop_v1: 7 wo with only 1 full-loss. exit150_full25_v1: 6 wo ALL full-loss.",
    "stated_correctly": "full15 write-off 5.9% of which full-loss 5.9% / partial 0.0%; bank15 write-off 50.0% of which FULL-LOSS only 13.6% and PARTIAL 36.4%.",
    "conclusion_UNCHANGED_mechanism_SHARPER": "Realised PnL per position already accounts for whatever was banked, so the money comparison is unaffected: full15 +0.26 vs bank15 -6.01 = +6.27U/pos, direction of the round-17 replay unchanged. What changes is the stated MECHANISM and it gets MORE favourable to the ladder design: bank15's ladder DOES bank (8 of its 11 write-offs were partial, averaging -3.61U rather than -20U) - IT JUST BANKS TOO LITTLE TO MATTER. full15 converts those same cohorts into real closures by selling 100% at the first tier.",
    "second_trap_in_the_same_table": "bank15's CLOSED (non-write-off) positions average -3.95U/pos while full15's average +1.53U/pos. That is NOT a performance difference either: the closed SETS are different by construction. bank15 does not close at +15% (it sells half and rides), so its closed set is dominated by stop/time exits while full15's is dominated by its take-profit. Comparing 'closed mean' across arms with different exit paths is MEANINGLESS. Only realised PnL per position is comparable.",
    "corrections_owed": "The mis-framed contrast appears in the records for rounds 17, 23, 25 and 26 and in this checkpoint. The CONCLUSION in each is unaffected; the stated MECHANISM is. This entry carries the corrected form.",
    "pattern_third_self_correction_in_three_rounds": "round 25 an outcome-identity merge list confounded by write-offs; round 26 a vacuously-true leave-one-out check; round 27 this. COMMON CAUSE: metric semantics ASSUMED rather than checked. Discipline that would have caught all three: before using a derived metric as evidence, DECOMPOSE IT AGAINST THE UNDERLYING MONEY at least once."
  },

  "ROUND_26_TOKEN_SELECTION_CANNOT_BE_LEARNED_FROM_46_TOKENS": {
    "where_this_went": "Round 25 put 56.9% of PnL variance on TOKEN identity (vs 14.6% on arm), so token selection is the highest-leverage area. Epoch: 46 tokens (36 with a usable first-entry snapshot), 7 winners, 39 losers, total -18,753.1U.",
    "winner_vs_loser_at_first_entry": "mcap winners med 889,300 vs losers 28,540 (31.2x); trades 593 vs 59 (10.0x); vol 30,460 vs 3,599 (8.5x); liq 77,920 vs 43,100 (1.8x); bp 70.8 vs 82.7; age_min 4.06 vs 3.90. CHAIN: solana 6 winners/18 losers (-4,927.9U); bsc 1 winner/18 losers (-13,279.9U = 70.8% of the total loss); robinhood 0/3.",
    "no_rule_keeps_all_winners": "No single token-level exclusion keeps all 7 winners except the trivial 'trades >= 0' (no exclusion at all).",
    "the_tempting_candidate": "first-entry mcap <= $28,300 covered 14 tokens containing ZERO winners while 6 of 7 winners sat above it: mcap >= 2.83e4 gives -6,707.2U versus -18,743.9U actual = +12,036.6U of loss avoided. At face value the largest single lever found this session.",
    "PERMUTATION_TEST_KILLS_IT": "Shuffle the token outcomes 4,000 times and for each shuffle search every possible cut for the best achievable exclusion: permutations where the BEST cut did at least as well as the real one = 4000/4000 = 100.0%. EVERY shuffle produced a cut as good or better. With only 36 tokens and free choice of cut point, a gain that size is GUARANTEED BY CHANCE. 'Zero winners below $28,300' is a property of the search, not of the market.",
    "the_trap_to_remember": "The POSITION-level version looked convincing and was also misleading: token-clustered 90% CI [+2.295,+10.623] EXCLUDES ZERO, kept 15.2% write-off vs dropped 65.7%. But that interval is CONDITIONAL on a cut point chosen by searching the same data, so it does not carry the significance it appears to. CLUSTERING FIXES THE DEPENDENCE PROBLEM, NOT THE SELECTION PROBLEM.",
    "supporting_checks_consistent_with_artifact": "not a pure chain effect (within BSC low-mcap 0 winners/-10,556.8U vs high 1 winner/-2,723.2U; within Solana 0 vs 5 winners) which is exactly why it looked convincing; not the activity floor restated - r(mcap, trades) across tokens is only +0.145.",
    "SECOND_ERROR_OF_MINE_CAUGHT": "My leave-one-token-out check printed 'removals that still leave ZERO winners: 36 of 14' and I initially read it as strong evidence. It is TRIVIALLY TRUE - removing a loser from a set that already contains zero winners obviously leaves zero winners. The test was vacuous as written and the count exceeded the set size because I iterated over all tokens rather than the low-mcap set. Do not trust this check in this form.",
    "CONCLUSION_and_line_closed": "Token-level exclusion rules CANNOT be validated from this epoch. Any cut searched over 36-46 token outcomes will look good and there is no out-of-sample route with this few tokens. This is the SECOND line closed in two rounds: (a) prune/merge the arm fleet - CLOSED (311 distinct contracts; differences unexercised not duplicated); (b) token-level exclusion filters - CLOSED (unvalidatable at n=36-46). The binding constraint is the NUMBER OF INDEPENDENT TOKENS (effective n ~30). Learning token selection requires MORE TOKENS, not more analysis of the same 46."
  },

  "ROUND_25_EFFECTIVE_N_IS_30_NOT_2256": {
    "variance_decomposition": "token identity eta^2 = 56.9% (46 tokens); cohort (token x snapshot) = 77.9% (405); ARM identity only 14.6% (174 arms). Positions per token: median 57, max 118.",
    "Kish_effective_n": "2,245 settled positions over 46 tokens with median 57 positions/token gives Kish effective n = 30.0. A per-position statistic quoted at n=2,245 is really about 30 INDEPENDENT observations. Every interval computed this session was already token-clustered so those stand - this quantifies WHY they are wide and sets a hard ceiling on what this epoch can teach.",
    "PRIORITY_ORDERING_derived": "token selection (56.9%) > entry timing (cohort adds ~21pp to 77.9%) > exit contract (14.6%). Consistent with everything since round 17: exit side had almost no headroom, entry floors moved the write-off rate, and run-up (an entry-timing feature) was the strongest marker after activity. DO NOT quote per-position statistics at n>30 for this epoch without clustering."
  },
  "ROUND_25_82pct_OF_POSITIONS_ARE_REPLICATION": {
    "numbers": "2,256 settled positions but only 406 DISTINCT entry decisions (cohorts) = 5.56 positions/cohort (median 2, max 50). Positions beyond the first on their cohort: 1,850 = 82.0%. Within-cohort PnL spread: MEDIAN 0.00U (p90 22.57, max 42.85) - for most multi-arm cohorts every arm realised the SAME result.",
    "fragmentation": "174 arms hold settled positions, median 9 each; 125 of 174 (72%) are below the 20-settled readability threshold, holding 871 positions between them. The fleet is simultaneously over-replicated in outcomes and under-powered per arm."
  },
  "ROUND_25_MERGE_HYPOTHESIS_TESTED_AND_REJECTED": {
    "naive_reading": "'82% of positions are duplicates - merge them.' This does NOT hold.",
    "confound_I_introduced_and_caught": "Pairing arms on identical (PnL, close_reason) produced a '50-arm provably identical group' that included the round-19 floor arms, which is implausible. CAUSE: a WRITE-OFF forces PnL = -stake and an identical reason, so any two arms written off on the same cohorts look trivially identical, and union-find chained those spurious pairs into one giant component. Excluding write-offs fixed it.",
    "second_check_outcome_identity_is_weak": "Of the 861 shared cohort-outcomes used to declare 114 pairs identical: market_mark_hard_stop 48.7%, max_hold 30.9%, trailing 13.1%, decay 6.7%, vol_scaled_stop 0.6%. Only 30.9% is the time exit and 0 of 114 pairs rest ONLY on max-hold, so the pairs are not merely untriggered. BUT 48.7% is the COMMON hard stop, which arms share by design - two arms agreeing there shows the shared rule bound first, not that they are the same strategy. Only ~20% of the evidence involves a rule that differs between arms. I DID NOT ACT ON IT.",
    "SAFE_TEST_contract_identity": "325 registered arms -> 311 DISTINCT contracts. Only 8 contracts shared by >1 arm, covering 22 arms holding just 28 positions (1.2%); 5 of the 8 duplicate groups hold 0 positions. THE ARM FLEET IS NOT MADE OF DUPLICATES AND THERE IS ESSENTIALLY NOTHING TO MERGE."
  },
  "ROUND_25_WHAT_THE_TWO_RESULTS_MEAN_TOGETHER": "The arms are CONTRACTUALLY DISTINCT (311 contracts) but BEHAVIOURALLY INDISTINGUISHABLE IN OUTCOME (arm eta^2 14.6%, median within-cohort spread 0.00U). The reason is NOT duplication: ~80% of exits are resolved by rules the arms SHARE (common hard stop 48.7% + time exit 30.9%), so the fleet's contract diversity is largely UNEXERCISED. Consistent with round 17 (hard stop dominant, 289 of 885 closes, gap-through fires stops early). IMPLICATION: arm proliferation is not the defect, and pruning would be both unsafe (nothing is a true duplicate) and ineffective (the differences are untested, not absent). The binding common rules are what suppress expression of the fleet's diversity.",

  "ROUND_24_DERIVED_FEATURE_SCREEN": {
    "what": "Nine point-in-time derived features built from the 20-minute pre-entry window plus the entry snapshot, screened against the WRITE-OFF label (2,369 positions / 37 tokens, base rate 32.2%) with tertile separation + token-clustered bootstrap + drop-the-best-token. This is the objective's 'derived/approximate feature' direction. Round 18 had screened the WRONG label (+15% touch); write-off is the one rounds 19/20 actually move.",
    "survivors": ["liq_trend +42.2pp CI [+0.249,+0.582]", "vol_trend +33.9pp CI [+0.139,+0.520]", "buy_pressure +42.7pp CI [+0.258,+0.589]", "mcap_liq -43.2pp CI [-0.626,-0.234] (the only MONOTONIC one: 76.2 -> 18.3 -> 2.4)"],
    "rejected": ["turnover", "price_vol_pct", "frames_in_window", "holders and liq_per_holder (not populated, 0 usable)"],
    "CHAIN_CONFOUND_applied_to_all": "This device's write-offs are ~100% BSC, so a feature that merely separates chains looks powerful. Within-chain: liq_trend +42.2 -> +16.8pp (BSC) / +14.0pp (SOL) so ~60% was chain mix; vol_trend +34.1 -> -0.4pp on BSC (DEAD) but +17.2pp on SOL; buy_pressure +42.4 -> +53.9pp on BSC (STRONGER) / +3.2pp SOL; mcap_liq -43.2 -> -25.7pp BSC / -18.3pp SOL but non-monotonic on both (BSC 74.9/88.4/26.8)."
  },
  "ROUND_24_BUY_PRESSURE_strongest_marker_but_REDUNDANT": {
    "feature": "buy_pressure = buys_5m/(buys_5m+sells_5m)*100 on the entry snapshot (rolling 5-minute figure, so point-in-time by construction).",
    "strength_on_bsc": "1,038 positions, 19 tokens, 63.3% write-off. Token-clustered bootstrap WITHIN BSC +0.539, 90% CI [+0.337,+0.708] EXCLUDES ZERO. Leave-one-token-out +0.487..+0.613, EVERY removal still positive. Quintiles show a SHARP THRESHOLD not a gradient: q1 30.4% wo (-6.59U/pos), q2 26.1% (-6.00), q3 82.6% (-16.78), q4 83.6% (-16.04), q5 93.3% (-18.40). Threshold at bp ~83%. A cap would cut the BSC book from -13,264.6U to -1,772.2U at bp<=75 (86.6% reduction).",
    "WHY_IT_WAS_NOT_SHIPPED": "It is largely ALREADY CAPTURED by the round-19 activity floor. r(buy_pressure, trades) = -0.631, and 'bp high & trades>=30' has n=3. The activity floor (trades>=30) already keeps only 232 of 1,038 BSC positions, of which 229 are bp-low (21.8% wo) and 3 are bp-high. So a buy_pressure cap on the surviving book would remove just 3 positions - negligible, and not worth a new correlated arm on a book with no per-token concentration limit.",
    "THE_REAL_VALUE": "It independently CORROBORATES the activity floor's mechanism from the other direction: the BSC death zone is ONE-SIDED BUYING WITH FEW TRADES - a pool being pumped with almost no two-sided flow. Two independent features converging on the same population is evidence the round-19 floor targets the right thing, not a new lever.",
    "residual_left_open": "Even after the activity floor, bp-low BSC positions still show 21.8% write-off. That residue is the next honest target; buy_pressure does not address it and nothing screened this round does."
  },

  "ROUND_23_READOUT_TOOL": {
    "commit": "682926c (pushed)",
    "tool": "scripts/experiment_readout.py (new, tracked). One command answers 'is any experiment readable yet, and what does it say' - previously done with ad-hoc SQL each round.",
    "DESIGN_POINT_that_matters": "paired_arm_ab.py pairs two EXIT carriers within a cohort, which is right because they share the entry opportunity. That design is WRONG for the ENTRY floors: a floor arm enters a SUBSET of the control's cohorts, so within-cohort pairing silently drops exactly the cohorts the floor rejected - the ones the hypothesis is about. Pairing would have hidden the effect it was meant to measure. So the readout applies a different design per kind: exit -> paired within-cohort diff + drop-the-top-token stress; floor -> SET-DIFFERENCE using the cohorts the arm refused BY ITS OWN FLOOR (from recorded outcomes), then measuring the control's own settled positions on those cohorts. It prints NOT READY and no verdict below the settled threshold (default 20 per side)."
  },
  "ROUND_23_INTERIM_READINGS_all_sub_threshold_NOT_verdicts": {
    "exit150_full15_v1_vs_bank15_plus15": "full15 settled=16, -0.00U/pos, win 81.2%, write-off 6.2% | bank15 settled=22, -6.01U/pos, win 27.3%, write-off 50.0%  <- THE STANDOUT, matches round 17's prediction that full capture at +15% beats leaving 50% riding",
    "exit150_full25_v1_vs_bank25_plus25": "full25 settled=14, -6.89U/pos, win 50.0%, write-off 42.9% | bank25 settled=22, -7.01, win 36.4%, write-off 50.0%  <- almost NO separation, which round 17's replay did NOT predict; the capture-fraction effect may be concentrated at the +15% level rather than being general. WATCH THIS.",
    "exit150_widestop_v1_vs_bank15": "widestop settled=10, -8.35U/pos, write-off 70.0% | bank15 22, -6.01, 50.0%  <- WORSE, consistent with rounds 120-16/120-17 having twice weakened the wide-stop argument",
    "activity_floor150_t30_v1": "settled=10, -4.72U/pos, win 20.0%, write-off 10.0% | control 26, -9.71, 19.2%, 42.3%",
    "activity_floor150_v5k_v1": "settled=8, -5.71U/pos, win 25.0%, write-off 12.5% | control 42.3%",
    "runup_floor150_r15_v1": "settled=9, -3.87U/pos, win 22.2%, write-off 22.2% | control 42.3%",
    "runup_floor150_r15a30_v1": "settled=7, -1.90U/pos, win 28.6%, write-off 14.3% | control 42.3%",
    "observation": "EVERY floor shows a much lower write-off rate than the control (10.0-22.2% vs 42.3%) - the specific mechanism each was built for. But every number here is sub-threshold and NOT a verdict."
  },
  "ROUND_23_COUNTERFACTUAL_verified_two_ways_but_rests_on_n3": {
    "claim": "For activity_floor150_t30_v1 the floor rejected 19 cohorts and the control itself traded 3 of them at -20.00U/pos with 100% write-off.",
    "verification": "method A (recorded outcomes = floor reason): 19 cohorts, 3 settled, -20.00U/pos, 100% wo. method B (independent: cohorts the control traded but the arm never did): 22 cohorts, 22 settled, -10.84U/pos, 45% wo. Both agree the avoided set is deeply negative.",
    "why_they_differ": "A isolates rejections attributable to the FLOOR; B also includes cohorts the arm missed for unrelated reasons (concurrency, single_token_lifetime_entry, or the arm not existing yet at that frontier). B is an upper bound on scope, not the floor's effect.",
    "HONEST_CAVEAT": "A's avoided set is only 3 positions. The floor rejected 19 cohorts but only 3 were opportunities the control would actually have taken - the control has its own gates. The -20.00U/pos figure is SUGGESTIVE, NOT ESTABLISHED, and the readout correctly refuses a verdict for it."
  },

  "ROUND_22_LANDED_ADAPTIVE_CADENCE": {
    "commit": "7b40eb5 (pushed)",
    "what": "observation_leases145.record_frame gains an optional `content` param; cadence_seconds backs the next due time off on an information-free sample: 0-2 unchanged -> 15s, 3-5 -> 30s, >=6 -> 60s CAP, immediate reset on any change.",
    "safety_constraints_implemented_and_tested": ["back off ONLY when price AND volume AND liquidity are ALL unchanged (a volume-only change is 3.2% of samples and resets the cadence)", "capped at 60s with immediate reset, so worst-case detection delay for a new move is one interval", "content=None reproduces the previous FIXED cadence exactly, so it is reversible per caller"],
    "durability_and_observability": "unchanged_run persists through dump_state/restore_state so a restart does not silently reset every backoff; last_content is deliberately NOT persisted (run restarts at 0 = conservative). bounded_summary now reports unchanged_run, cadence_seconds, content_known.",
    "verified_live": "cadence values live [15,30,60]; 24 slots at 15s, 1 at 30s, 5 at 60s; content_known 30/30. Requests/min 187.2 -> 183.3 (essentially flat). Implied request cost across the 30 slots 120 -> 103-105/min = 12.5-14.2% FEWER REQUESTS for the same slots.",
    "coverage_quality_did_NOT_regress": "input_ready:window30 share 68.291% -> 70.190% -> 70.993% (improved slightly). trajectory accepted 47,226 -> 53,336; ready 32,251 -> 37,865. signal second_wave 16 -> 18.",
    "tests": "8 new tests in tests/test_observation_cadence.py, plus the two DEDICATED observer regression suites (test_observation_leases145.py, test_observation_leases145_runtime.py) and the related suites all pass."
  },
  "ROUND_22_CORRECTION_my_3_42x_estimate_was_TOO_HIGH": {
    "claim": "Round 21 projected matching cadence to the source update rate would cover ~3.42x more distinct pools. The REALISED effect is ~12-14% fewer requests, not 3.42x.",
    "why_it_was_a_measurement_population_error": "(1) the 70.8% information-free rate was measured over tokens with >=20 snapshots - the DENSE-pool history, which is dominated by pools that sat in a slot a long time precisely BECAUSE they were quiet or dead. (2) volume_5m_usd is a ROLLING 5-MINUTE SUM, so it changes on almost any trade, so under the strictly-safe criterion the backoff only engages for pools with essentially no trading. (3) the live slots show median unchanged_run of 0-1, i.e. most occupied pools ARE updating.",
    "correct_statement": "70.8% of samples in the dense history are information-free, but the LIVE SLOT POPULATION at any instant is mostly active, so only a minority of slots can back off.",
    "coverage_gain_UNPROVEN": "the distinct-pool-per-bucket series is strongly TRENDING (543 -> 939 -> 796 -> 612 -> 587 across the pre-change window), so a naive before/after comparison is confounded. With one partial post-change bucket there is NOT enough data to claim a coverage gain either way.",
    "narrower_criterion_declined": "backing off when PRICE alone is unchanged would engage far more often, but it would also back off across volume-only changes (3.2% of samples, real information). Not worth taking without its own evidence; the conservative criterion stands."
  },

  "ROUND_21_OBSERVATION_BUDGET_IS_3_4x_UNDERUTILISED": {
    "finding": "observation_leases145.record_frame sets next_due_at = observed_at + TARGET_SECONDS (15) regardless of whether the source has anything new. Measured over 13,651 consecutive same-token snapshot pairs (237 tokens with >=20 snapshots): price AND volume both changed 25.7%, volume-only 3.2%, price-only 0.3%, and NOTHING changed (price+volume+liquidity all identical) 70.8%. So 70.8% of polled requests return no new information. Matching cadence to the source's real update rate would cover ~3.42x MORE DISTINCT POOLS for the SAME request budget - no budget increase needed.",
    "worst_where_it_matters": "TRADED tokens have a HIGHER repeat rate than untraded: traded median 82.2% (p25 77.3, p75 85.0, 64.5% of tokens >80%) vs never-traded median 66.7%. 30 of 31 traded tokens exceed 50% repeats; 20 of 31 exceed 80%. Worst case bsc:0x64a6c4c1 took 1,085 snapshots at 89.7% repeats and produced 67 positions. 21 dense pools recorded ZERO information change across 668 polls and NONE of the 21 ever produced a position.",
    "run_lengths": "consecutive no-information runs: p50 3, p90 10, p99 31, max 55. Runs of >=5 waste 7,834 polls.",
    "NOT_an_accuracy_defect_CONTAINMENT_VERIFIED": "record_frame rejects a frame only on observed_at <= prior (a TIMESTAMP test), and a live frame shows observed_at == ingested_at == recorded_at exactly, so observed_at is our receipt time and repeats DO advance the clock. In the live trajectory144:state, 60 pools have frames>=3 (all 60 formed window_30) and 26 of those (43.3%) have <=1 distinct price across their ENTIRE frame history; across the 60, 1,737 frames contain only 378 distinct prices (78.2% repeats). BUT containment holds: the 26 static pools emitted 0 signals and produced 0 positions and carry phase=None, while the 34 active pools emitted 14 signals and hold 1,085 positions. The phase/flag machinery never engages on zero-variation pools. So there is NO accuracy defect to fix and no reason to touch the trajectory engine's frame handling.",
    "self_correction": "I first computed '81% of pools have a single price' and caught that it was contaminated by the 108 one-frame pools, for which the statement is trivially true. Corrected figure is 26 of 60 eligible pools. The first number overstated the defect by ~2x.",
    "window_formation_is_healthy": "trajectory144:state counts show 29,657 of 44,380 accepted observations (66.8%) produced input_ready:window30; 14,723 input_unknown:window30. Window formation is NOT the leak.",
    "hypotheses_killed_this_round": "slot waste (all 30 slots occupied, 11 held by open positions, only 4 of 30 = 13% yield <=1 frame then SOURCE_NO_UPDATE); dense-pool waste (40 of 68 dense pools never produced a position but account for only 2,876 snapshots = 7.3% of observation)."
  },
  "ROUND_21_ADAPTIVE_CADENCE_DESIGN_not_implemented": {
    "why_deferred": "the observation supply is the HIGHEST-BLAST-RADIUS surface in the system - it feeds every arm at once, and six forward experiments (exit150_*, activity_floor150_*, runup_floor150_*) are accumulating evidence a cadence regression would quietly corrupt. Design is specified and containment evidence is in hand; it should land as its own change with its own verification.",
    "constraints": ["back off ONLY when price AND volume AND liquidity are ALL unchanged (volume-only changes are 3.2% of samples and are real information)", "modest capped backoff 15s -> 30s -> 60s cap, with IMMEDIATE reset on any change, so worst-case detection delay for a new move is one backoff interval", "must not thin the ACTIVE pools - the trajectory window needs >=3 frames within 30s, so an over-aggressive backoff would destroy it. Verify, do not assume."],
    "success_metric": "distinct pools covered per hour at unchanged request volume, with NO regression in input_ready:window30 share (currently 66.8%)."
  },

  "ROUND_20_DIAGNOSIS_latency_and_funnel": {
    "funnel": "10,089 discovered -> 9,531 observed (94.5%) -> ONLY 37 EVER ENTERED (0.4%). 37,774 evaluations -> 1,710 positions (4.53%). Settled 1,318 at -11,493.58U (-8.72U/pos). The bottleneck is observation capacity between observation and judgement, NOT a threshold defect.",
    "gate_distribution": "cohort_observation 34.38% + pattern_observation 22.77% = 57.15% is observer bookkeeping that can NEVER admit; no_active_matching_entry_policy 25.85%; entry_pool_liquidity_absent_curve_stage 7.66%; invalid_exact_asof_market_snapshot 5.17%; entry_pool_liquidity_below_configured_floor 3.04%; entry_pool_liquidity_unknown 1.10%; entry_snapshot_too_old 0.03%. So the gate distribution does NOT show an over-strict filter.",
    "latency": "observed->ingested p50 0.03s; observed->recorded p50 0.63s; observed->evaluated p50 1.21s (p90 11.33s); entry snapshot observed->opened p50 0.18s / p90 2.57s. THE PROCESSING PATH IS NOT THE BOTTLENECK.",
    "real_speed_defect": "discovery->first-observation TAIL: p50 8.05s but p90 1,500.95s (25 min) and p99 8,517s (2.4h). Same observation-capacity limit expressed as latency.",
    "self_correction": "I first read entry_execution/entry_signal - 1 as a 'latency premium' at 99.5% of positions. It is EXACTLY 4.0000% at every percentile (p10=p50=p99=max) - the frozen BUY_SLIP=0.04 cost model, not latency. Do not re-report it as an execution-quality defect.",
    "delay_confound_stated": "Entering LATER does better (after 1h: -1.31U/pos, 0.0% write-off) BUT that group is conditioned on surviving an hour, so it is NOT evidence that faster entry would help. Recorded so it is not misread as a speed recommendation."
  },
  "ROUND_20_SHIPPED_RUNUP_FLOOR150": {
    "commit": "bc4dabc (pushed)",
    "arms": ["runup_floor150_r15_v1 (run-up <= 15%)", "runup_floor150_r15a30_v1 (run-up <= 15% AND trades >= 30)"],
    "module": "src/memetrader/runup_floor150.py (new)",
    "marker": "runup = current price / earliest observed price in the 20 minutes before the decision - 1. The 20-minute window is deliberate: the acceptance loop's own `history` (store.py:27614, LIMIT 80) holds exactly that window, so the cap costs ZERO extra queries. Verified live: ZERO runup_floor_window_unknown rejections.",
    "measured_basis": "write-off rate jumps from 0.6% at a 15% cap to 6.0% at 20% and 24.8% uncapped (1,712 positions). Token-clustered significant BOTH ways: write-off +0.322pp CI [+0.082,+0.565]; PnL -4.851 U/pos CI [-9.491,-0.055]. Not the survival confound (r=-0.116 with entry delay).",
    "second_pass_correction": "The money effect ONLY clears the bar as a low-vs-high contrast. A cap contrast gives +3.96 U/pos CI [-0.59,+8.42] because it dilutes by putting the ambiguous middle in the dropped group. I nearly recorded the finding as failing; the tertile contrast is significant.",
    "complementarity_with_activity_floor": "quadrants: runup ok & trades>=30 -> 0.3% write-off at -3.36U/pos; runup high & trades<30 -> 64.1% write-off at -12.48U/pos. Combined book -11,434U -> -1,860U with win rate 13.9% -> 23.6%.",
    "honest_limits": "It is TOKEN SELECTION, not entry timing (within tokens: median diff exactly 0.000, positive in only 6 of 15; acts on 12 of 37 tokens). Level chosen in-sample. The kept book STILL LOSES -2.88U/pos. Forward experiment only, NOT a validated fix.",
    "verified_live": "325 additions; both arms at OWN frontier 38633; control unchanged at 0; arms trading (6 positions each); floor BITES: 6x runup_floor_exceeded each alongside 6x accepted.",
    "discipline": "screen reuses the round-19 hook, returns None for every other arm, sits after signal validation, distinct auditable rejection reasons (runup_floor_exceeded / runup_floor_window_unknown / activity_floor_trades_not_met), missing evidence never admits. No existing strategy, stop, hold or exit contract changed. 120 tests pass."
  },

  "ROUND_19_LANDED_ACTIVITY_FLOOR150": {
    "commit": "024b0d6 (pushed)",
    "arms": ["activity_floor150_t30_v1 (buys_5m+sells_5m >= 30)", "activity_floor150_v5k_v1 (volume_5m_usd >= 5000)"],
    "module": "src/memetrader/activity_floor150.py (new)",
    "why_entry_arms": "unlike EXIT150 these are ENTRY arms and DO go into alpha149.SPECS - they must, so the shared acceptance loop can screen them. Confirmed by round 18: alpha149.py:2283 iterates SPECS generically and an arm fires when flags.get(kind) is set.",
    "one_factor_design": "reuse the control's kind ('merged_multi_setup') so they fire on the same mechanism flags and get the same frozen signal, and clone the control's exit contract verbatim (stop -0.2, trail .30/.15, hold 15, tp [], 2U, isolated_cohort_observer). Control = alpha149_merged_multi_setup_fast_v1, chosen because merged_multi_setup is the highest-volume generic mechanism (6 arms x 123 emits/374 cohorts) and round 16 already characterised it. Verified on the BUILT policy: every exit-contract field equal, and on all shared keys only identity/label fields differ.",
    "enforcement": "opt-in by arm id in the shared cohort-acceptance loop (store.py), placed AFTER signal validation so a recorded rejection means exactly 'a valid signal existed but the pool was too quiet' rather than 'this arm had no signal'. reject_reason returns None for every arm that is not ours - asserted against the whole 158-arm registry.",
    "auditability": "the floor is declared on each arm's own entry_filter.activity_floor (visible in the registered policy body) AND the rejection reason is distinct: activity_floor_trades_not_met / activity_floor_volume_not_met.",
    "missing_evidence": "never admits. Coverage is complete (0 nulls in 35,349 snapshots) so this is a safety net.",
    "verified_live": "321 -> 323 additions; both at OWN frontier 36360; control frontier unchanged (append-only respected). Arms TRADE: t30 5 positions, v5k 2 positions within ~3 min. Floor BITES: in cohort feature_json -> outcomes, t30 shows 1x activity_floor_trades_not_met + 7x ready; v5k shows 5x activity_floor_volume_not_met + 4x ready; the control shows ZERO floor reasons. v5k rejects more than t30, matching the measured pass rates (47.2% vs 59.3%).",
    "correction_to_my_own_expectation": "I first expected the reason in chain_meme_trader_v6_entry_evaluations.reason, but store.py:28327 persists observation_reason ('cohort_observation'/'pattern_observation') there, NOT the per-arm reason. The per-arm reason lives in the cohort outcomes map. Verified empirically rather than assumed.",
    "tests": "108 pass (tests/test_activity_floor150.py is new, 11 cases)."
  },

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
  "next_action": "P0-NEW read exit150_full15_v1 at 20 settled (17 now) - realised PnL per position, decompose any write-off claim into full-loss vs partial (round 27 rule). P0-1 KEEP THE EXPERIMENTS RUNNING - they are the only source of new information now and need WALL-CLOCK TIME, not more analysis. Rounds advance ~15-30s of wall clock while positions settle slowly, so do not expect verdicts soon and do not manufacture work to fill the gap. P1 the residual after the activity floor: bp-low BSC positions still show 21.8% write-off. STANDING NOTE: for any entry-feature query STATE WHICH LANE IT COVERS - a join on entry_snapshot_id silently excludes the native_protocol_model lane (11 positions, entry_snapshot_id=0 by design, reason later_observed_protocol_model_paper). STANDING RULE: for any partial-exit arm NEVER quote a write-off rate as a loss rate, and NEVER compare 'closed'-set means across arms with different exit paths. STANDING RULE: before using a derived metric as evidence, DECOMPOSE IT AGAINST THE UNDERLYING MONEY at least once. DO NOT re-open: arm pruning (r25), token-level exclusion search (r26), the capital hypothesis (r28), slot turnover (r29), or the dense-episode-free lane (r30 - it is the native_protocol_model lane, 1 position per token, -0.98U/pos, not widenable). DO NOT quote per-position statistics at n>30 without clustering.",
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
