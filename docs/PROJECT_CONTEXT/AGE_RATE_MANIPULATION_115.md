# Age-rate manipulation concentration audit115

REPLY_TO: C2C-20260909-AGE-RATE-MANIPULATION-CONTAMINATION-115
Disposition: MANIPULATION_CONTAMINATED / RESEARCH_REQUIRED; reversible NEW-entry pause applied, not a finding that every themed token is a proven scam.

## Independently reproduced ledger

Frozen cutoff 2026-09-09T20:43:29.727969Z, current funding-20260906-v002-final-1000. Actual closed/written-off parent positions joined by entry_snapshot_id; grouping uses frozen provider baseToken symbol BNC4 or name 4Stock on BSC only. Current names and future microstructure are not decision features. Tail below means realized PnL >=5U, not chart MFE.

|BSC sensitivity|Terminals|Realized U|Tails|
|---|---:|---:|---:|
|All|57|691.511344556|10|
|BNC4/4Stock themes|11|723.234943662|9|
|Excluding these themes|46|-31.723599107|1|

The remaining best tail is +6.492410029U. Difference from Lead's 56/+692.622 and45/-30.613 is the new non-theme BUIDL cohort94675 terminal -1.110421836U. This is an ex-post concentration sensitivity, not a validated causal decontamination rule or theme blacklist.

|Entry UTC date|BSC raw N / U|Excluding themes N / U|
|---|---|---|
|Sep7|10 / +2.254065393|10 / +2.254065393|
|Sep8|37 / +358.406080641|30 / -28.791308800|
|Sep9|10 / +330.851198522|6 / -5.186355700|

Other-chain parent totals: Robinhood47/-3.769461025U; Solana74/-75.296537998U. The BSC theme exclusion is not applied to same-name Solana tokens. Full date/chain rows and position distribution are in summary.json and rows.json.

## Evidence and limits

All11 themed positions match their frozen cohort exact pool; all11 entry snapshot clocks satisfy observed<=ingested<=recorded<=opened. Exact local references for the three Lead-described microstructure cases:

|Token suffix|Entry snapshot|Original pool|Opened UTC|m5 volume / buys / sells / change|
|---|---:|---|---|---|
|0x5138...9d0d|2102057|0x7D12b18aC5475Ad7429cF32dAb9DFCc4586F0b2d|Sep9 00:32:32.871525|34665.38 /4/1 /-94.84%|
|0x4f4a...98b8|2177144|0xeaa9Db23b350E5C32f3553F421619038119b3536|Sep9 04:05:33.960044|34953.87 /5/1 /-94.70%|
|0xbf4f...4a67|2183164|0x2b9EEA3FCbd78B183238732E53512566A1816359|Sep9 04:23:53.116554|35681.37 /6/1 /-95.28%|

Lead reports retrospective trade lists for those pools: 16/15/16 trades, buy USD about11.45k/10.86k/11.46k versus sell30.70k/30.55k/30.51k, one ~30k sell, a single tx_from per list. These signed amounts/wallet claims are LEAD_REPORTED, not independently reproduced here from raw trade payloads. Fourth query rate-limit and six other similar tails remain UNKNOWN/MANIPULATION_SUSPECTED. A shared tx_from may be a router/custody intermediary; it alone does not establish one beneficial owner or proven scam. Later-retrieved trades cannot be backdated into entry safety availability.

The independent ledger concentration plus absent verified preentry breadth makes normal-market Alpha claims unsupported. Preserve all simulated profits; do not erase them or describe excluded PnL as recovered capital.

## Applied action and verification

At 2026-09-09T20:46:41.910951Z, existing convergence KV paused NEW entry for:
- resource_age_rate_candidate_v1
- dynamic_principal_recovery_runner_v2
- age_rate_half_runner_recovery_v3
- narrative_hold_recovered_runner_v2

No paired_entry_group dependencies for these four. failed_impulse_cooling_v1 remains unchanged: it consumes prior closed core-loss receipts, not simultaneous parent enrollment; source lineage alone is not a reason to pause it. Other independent mechanisms remain untouched.

Existing assessment enum remains INSUFFICIENT, with explicit visible assessment_note MANIPULATION_CONTAMINATED / RESEARCH_REQUIRED, evidence pointer and reversible research-pause reason. /api/live confirmed all four entry_paused=true and notes. strategy-universe response was captured but did not expose matching entry_paused fields in the bounded extractor; no claim of screenshot verification. Post-cutoff check: zero new selected-arm positions, zero open selected-arm positions at read. Existing exits are preserved regardless of this zero-open snapshot.

Transaction assertions checked effective pauses and identical digest before/after over registrations, activations, policy additions, funding/capital tables and selected positions/trades: f75976e079188a8f1762785806a0770b27d748b982495f88abc23f5ee5e0a49b. Only existing convergence KV changed. No restart, threshold/account registration, historical PnL rewrite, or Live change.

114 remains WITHDRAWN_BEFORE_REGISTRATION; registrar inert and startup registration removed by fbf51c2. Do not deploy funded pulse from aggregate proxies.

## Smallest remediation boundary

Existing capital_context computes net_quote_flow_raw/effective_breadth from qualified amountful rows, preserving causal ordering rather than treating counts as signed flow. Existing PumpSwapVaultFlowTracker is a Solana source, not proof BSC swap-wallet coverage exists. No complete BSC exact-pool signed-flow/breadth preentry source was established in this audit; no new request lane is deployed.

Reconsider enrollment only after prospective rare-candidate verification has exact pool/token identity, usable local availability clocks, signed buy/sell USD, distinct/effective breadth with router semantics, concentration and amount/timing regularity. Existing complete amountful evidence should be preferred. Supplemental public trades, if later approved/implemented, must share conservative provider budget, backoff and held priority; missing/stale/incomplete => WAIT. Strong single-actor giant-sell cycles are hazard evidence, not normal-coin absorption. No automatic re-enable from PnL or symbol exclusions. Validate normal-market forward coverage before a funded promotion.

## Durable artifacts

- data/research/manipulation115/rows.json: raw current-period parent ledger, frozen metadata/clocks
- data/research/manipulation115/summary.json: exact sensitivity and date/chain distributions
- data/research/manipulation115/applied.json: cutoff, selected arms, previous convergence control, invariant digest
- data/research/manipulation115/post.json: API readback and no-new-position check
- scripts/apply_convergence115.py: applied bounded governance transaction (do not rerun for monitoring)
