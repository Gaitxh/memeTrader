# Candidate routing root-cause79

REPLY_TO: C2C-20260909-TODAY-RIGHTTAIL-ROOTCAUSE-79

## Findings and correction to zero-decision interpretation

Read current /api/token for9 named cases (raw JSON under data/research/rootcause79), then join evaluation ledger by exact source snapshot ID from frozen78. Trace is current readback over those source IDs; hydration/API state is current, not backdated to78 cutoff. No API decision rows does not mean no generic/cohort/pattern processing.

|Case|Recorded evaluation types on78 snapshot IDs|Current hydration state|
|---|---|---|
|BITCAT|{'no_active_matching_entry_policy': 3, 'cohort_observation': 2, 'entry_pool_liquidity_unknown': 11, 'entry_pool_liquidity_below_configured_floor': 16}|hydrated|
|GME20|{'entry_pool_liquidity_below_configured_floor': 20, 'all_entry_accounts_cash_below_20usdc': 2, 'cohort_observation': 650, 'entry_pool_liquidity_unknown': 1, 'no_active_matching_entry_policy': 28, 'pattern_observation': 2704}|hydrated|
|Jacob|{'no_active_matching_entry_policy': 41, 'cohort_observation': 42, 'entry_pool_liquidity_unknown': 8, 'entry_pool_liquidity_below_configured_floor': 24, 'pattern_observation': 21}|hydrated|
|CLAWDHOOD|{'entry_pool_liquidity_below_configured_floor': 7, 'no_active_matching_entry_policy': 3, 'cohort_observation': 7}|hydrated|
|DUO|{'pattern_observation': 276, 'cohort_observation': 50}|NO_ROW|
|QUEST|{'no_active_matching_entry_policy': 5, 'cohort_observation': 4, 'entry_pool_liquidity_below_configured_floor': 8, 'pattern_observation': 3}|hydrated|
|CRIMECAT|{'entry_pool_liquidity_unknown': 3, 'all_entry_accounts_cash_below_20usdc': 2, 'cohort_observation': 2, 'no_active_matching_entry_policy': 1}|hydrated|
|tip|{'entry_pool_liquidity_below_configured_floor': 1, 'no_active_matching_entry_policy': 2, 'cohort_observation': 1, 'pattern_observation': 4}|hydrated|
|MUCHWOW|{'all_entry_accounts_cash_below_20usdc': 1, 'cohort_observation': 1, 'entry_pool_liquidity_below_configured_floor': 4}|hydrated|

## Per-case first disappearing stage

- Jacob:21 pattern observations already exist; parent reports20 old-rate-below-threshold and1 common-wait. Reawakening includes insufficient sequence, gap, age/buy-ratio/conditions. Therefore not a total routing blackout.26 valid-pool episodes in78; cross-pool quotes cannot be concatenated into one price path.
- QUEST:3 pattern observations; parent candidate_rejected once then common-opportunity-consumed twice; reawakening age gate3. This is cohort/rule eligibility, not missing dispatch. Consumed opportunity is existing one-episode semantics; no retry/threshold alteration.
- BITCAT:all32 source snapshots have general outcomes;2 cohort observations but0 pattern. First disappearance is promotion to persistent pattern observation/continuity, then11 unknown-liquidity/16 below-floor frames. Exact historical watch-cap denial versus expiry versus pool mismatch is not logged and cannot be reconstructed uniquely.
- CLAWDHOOD:17 frozen snapshots have3 no-active-policy,7 cohort,7 below-floor evaluations;0 pattern. Current API still0 decisions despite later data. This demonstrates distinct generic/cohort and watched-pattern routes. Historical watch-victim identity unavailable; cannot assert a specific cap denial.
- CRIMECAT:8 snapshots have2 cohort records,2 old generic cash-below20U,3 unknown-liquidity and1 no-active-policy. No pattern record. PumpPortal receipt is not pool price evidence;5 floor-qualified frames span two pools with poor strict-original continuity. Later same-token price is not proven original-pool executable gain.
- MUCHWOW:6 snapshots have1 cohort,1 historical generic cash-below20U,4 below-floor outcomes;0 pattern. Current last_seen Sep8 07:40:39Z; no new observation supplies current reawakening.
- DUO:current last_seen Sep7 16:06:55Z; current hydration row absent.276 historical pattern observations and4 positions are not Sep9 reawakening evidence. A new causal observation episode is required; parent historical loss does not test the new wave.
- tip:initial liquidity below1000 then much later floor-qualified anchor. It does receive4 later pattern observations; parent old-rate filter4, reawakening sequence/gap. Native economics remains prerequisite for below-floor phase, not permission to lower floor.
- GME20:78 exact raw snapshot1940309 already has>=1000 at Sep8 15:07:14.958188Z (Gecko liquidity20843.6846, pool0x34a638b2f1fd453e544c3ddff06b72ce5f7f3dca). Therefore the message79 assertion that first>=1000 was00:54 is not true under78 validated original-pool definition. Later chart/pool may differ. All13 recorded positions retain their historical outcomes; no curve-alpha claim from DEX entries.
- c26e local lookup unmatched;8735 was not found on supported chains in78. Lead identifies8735 as XLayer, outside current runtime three-chain scope; this report does not independently authenticate its external chain.

## Proven implementation defect and smallest fix

Runtime._remember_pattern_quotes keyed by token_id replaced quote unconditionally but retained old pair_address, pool birth/bucket and expiry. A new-pool single-pair Gecko receipt could erase an unconsumed original-pool frame, appear fresh to due selection, then fail exact-pool observer matching. This is a deterministic state inconsistency proven by code plus regression fixture, independently reviewed by routing79. It is not proof that each listed historical case traversed that branch.

Fix c3044be: replace quote only if incoming pair/pairs contains canonical watched pool; otherwise retain existing quote and count other_pool_quote_skips_since_start. No pool substitution, no new scheduler, no threshold, no watch-cap/TTL/reservation change. Original due-refresh cadence is restored for these conflicts; actual traffic may use previously suppressed existing cadence, not an increased configured budget. Passive cohort delivery still receives all original incoming quotes as before. Tests cover held/Solana case-sensitivity, multipool containing original, expiry/count and existing capacity/reservation tests.8 passed.

## Bounded old-token coverage and unproven causes

Current _shared_market_followup_schedule starts max(now+60s,birth+901s), expires birth+6h; hydration admits at most2 followups per round. Pattern slots expire15m (early/growth) or20m (mature); base3/4/3,total10/chain. These intentionally do not provide all-old-token monitoring. New external discovery/migration/metadata observations may reintroduce tokens, but no fresh observed trigger for DUO/MUCHWOW is present in the readback. Missing source receipt cannot be fixed by replaying their old data. No permanent watch or larger budget introduced.

A possible future event-driven reactivation must use a genuinely newly received source event, deduplicate identity/event, use existing hydration budget, and open a fresh exact-pool/as-of observation episode. No such new event has been demonstrated for these old-token cases; do not add a winner-specific route. Historical watch admission/expiry cause is not recorded per token, so attribution remains PARTIAL rather than invented.

## Deployment and boundaries

Controlled existing Paper launcher restart applied c3044be; web process preserved. This also loads previously tested76 clock/hash-semantics correction (71691b8), with per-instance verification unchanged and UNKNOWN preserved. No new strategy, funding reset, history rewrite or Live authority. Short runtime acceptance follows in this report; no claim all79 coverage problems are solved.

## Short runtime acceptance

Health running/current r6; /api/live and /api/performance returned normally. Immutable funding/registration/policy-addition tables hash unchanged (before_immutable/after_immutable.json). At short post-start sample:held_fetch102 samples p50 .817s/p95 2.243s/failures0;held_apply p95 .04756s;pattern4 samples p95 5.228s;hydration11 samples p95 4.974s;passive149 enqueued/148 processed/depth1/drops0;Dex pool_timeouts0/connect_errors0. Before longer-window held p95 2.825s andpattern9.880s are not a matched benchmark; no causal speedup claim.

Natural KV07:11:03Z records13 other-pool quote skips,57 sampled watches; nonheld perchain totals remain10 (BSC6/4/0,RH4/4/2,SOL6/4/0), preserving borrowing/reservations. This proves the corrected conflict branch occurs naturally, not which historical user token was affected or that right-tail capture improved. No extra provider/source or configured request budget; long-run economic/coverage validation remains unproven.

Disposition: ONE_ROUTING_DEFECT_FIXED_AND_LOADED; historical watch-denial attribution PARTIAL; old-token reactivation source coverage LIMITATION_CONFIRMED, no speculative permanent watch. Artifacts rootcause79 include API readbacks, trace, pre/post performance/funding digest,watch_acceptance.
