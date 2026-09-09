# Message90 staged implementation — IN PROGRESS

Reply-to: C2C-20260909-STRATEGY-SYSTEM-SAFETY-90.

## P0-A common Paper entry safety

Code audit of the current14 active policies finds isolated pattern/cohort enrollment
projects BUY through `_project_chain_meme_trader_market_entry`. This did not invoke
the older event `SafetyChecker.check`; the Jupiter-only baseline pretrade gate did
not cover this market-price contract. A signal-only asynchronous safety worker now
guards that common projection. Not yet deployed at this checkpoint.

Explicit GoPlus dangerous controls/honeypot flags and existing12% tax limit reject.
Honeypot simulation failure alone stays UNKNOWN rather than proving a honeypot.
Solana reuses dangerous-control assessment and explicit verified pool rejection;
missing LP-lock/custody knowledge is not a hard rejection of legitimate protocol
pools. No new global Jupiter exact-quote requirement. Robinhood supported provider
surface identity is checked, but external contract security is UNKNOWN: this is
not onchain bytecode verification or an assertion of safety.

Missing all reports waits; partial evidence without explicit danger may authorize
ordinary Paper with UNKNOWN visibly retained. PASS never means guaranteed safe.
Security acquisition uses existing source TTLs, one worker,128 pending cohorts,
256 cache entries. Successful acquisition is local availability time, not claimed
chain freshness. Failed refresh cannot renew an old report. Existing explicit
negative evidence rejects before any supplemental request.

Pending entries persist in KV and require a strictly later valid original-pool
frame after security acquisition. Original legacy intents stay ready while waiting,
and freeze their receipt only when authorized. No historical snapshot/fill rewrite.
Audit is append-only evidence keyed by cohort/status, independent of account fanout.

Validation so far:14 focused safety cases plus6 existing Paper execution cases
PASS (20 total). This is engineering validation only. Deployment/natural latency,
funnel counts and remaining90 stages remain outstanding.

Primary field semantics: https://docs.gopluslabs.io/reference/response-details and
https://docs.honeypot.is/ishoneypot . Missing values are not measured false;
generic simulation errors are not affirmative cannot-sell evidence.

## Remaining stages

P0-B exact flat selector integration and production equivalence remain pending;
standalone frontier fixture is not a deployed performance improvement. P1-A must
exit at15m when uncovered OR deteriorating, not AND. P1-B must recover debit from
actual partial-fill proceeds, never target-price arithmetic. P1-C reactivation,
P0-C local-only timing work remain pending. P1-D currently Shadow DATA_BLOCKED:
Pump held sell math exists but complete new-buy/immediate-sell USD cost contract
is not yet available; see STRATEGY_REVISION_FEASIBILITY_90.md. Pons issues are not
evidence about Pump. No new strategy is registered at this checkpoint.
