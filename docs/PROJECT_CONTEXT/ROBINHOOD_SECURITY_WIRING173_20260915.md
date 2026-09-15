# Robinhood pre-entry safety wiring 173 - 2026-09-15

## Diagnosis

After the Pump hydration repair, the highest controllable funnel loss moved to
the admitted-signal to Paper-position boundary. From `12:51:31Z` through the
read-only audit, 200 admitted arm decisions produced 148 positions. The missing
52 were not cash, liquidity, concentration or strategy-filter refusals: 51 had
terminal `EXPIRED_SECURITY_OR_NEXT_FRAME` evidence and one was still
`CHECKED_UNKNOWN`.

The loss was chain-specific. Solana projected 108/113 admitted decisions and
BSC 26/27, while Robinhood projected only 14/61. In the latest strategy window,
Robinhood projected 3/23 and 19 expired; Solana and BSC projected 24/24. Typical
Robinhood cohorts reached `CHECKED_UNKNOWN` in 7-57 seconds, then expired at the
90-second execution deadline. The unknowns recorded provider unavailability or
`no_usable_safety_fact`, not an explicit scam rejection.

The code had three separate EVM enrichment conditions in the hydration,
universe-followup and shared batch paths. Each listed Ethereum, BSC and Base but
omitted Robinhood, even though `SafetyChecker` maps Robinhood to GoPlus chain id
4663 and already has focused tests for that endpoint. In the pre-change window,
1,540 stored Robinhood snapshots contained zero execution-safety timestamps,
zero GoPlus reports and zero GoPlus error receipts. This is a collection wiring
defect, not evidence that every provider lookup returned no report.

## Change

`strategy.py` now owns one `is_evm_execution_chain()` capability predicate for
Ethereum, BSC, Base and Robinhood. `SafetyChecker.enrich_evm()` and
`enrich_evm_execution_fields()` use it, and all three runtime snapshot paths use
the same predicate. This removes the drift that excluded Robinhood and lets the
normal earlier snapshot path collect or explicitly fail to collect GoPlus
evidence before a strategy reaches the asynchronous pre-entry guard.

No safety rule is relaxed. A completely absent report remains UNKNOWN without
usable facts and cannot become a regular Paper buy; an incomplete report may
retain UNKNOWN status while authorizing Paper only when it contains the
existing explicit usable false-risk facts. Explicit hard risks remain REJECT.
HTTP batch size, cadence, priority, account funding and existing positions are
unchanged.

## Validation and forward guard

- Focused runtime tests exercise both BSC and Robinhood through the real
  token-universe followup path and assert the execution-safety enrichment call.
- The full pre-entry safety module test covers the shared chain predicate,
  Robinhood chain-id 4663, partial reports, UNKNOWN and hard rejection behavior.
- No historical snapshot, decision or trade is rewritten.

## Deployment and initial forward receipt

The existing Paper child was restarted under the unchanged supervisor at
`2026-09-15T13:45:05Z`; the runtime startup receipt is
`2026-09-15T13:45:08.534171Z`, PID 40884. The loaded `runtime.py` hash equals the
working-tree hash. `/health` returned HTTP 200 with runtime `running` and the
same funding version `chain-meme-trader/funding-20260906-v002-final-1000`.
Paper-only and the live lock remained enabled. Local release checks must bypass
the host HTTP proxy for loopback requests; the earlier 502 was the proxy, not a
ChainMemeTrader response.

The first forward window changed the failed boundary immediately:

- 7 Robinhood cohorts produced 31 admitted arm decisions and 31 positions.
- Four fresh worker fetches recorded `CHECKED_UNKNOWN`; each had an actual
  `goplus_evm` report and canonical provider surface, rather than provider
  unavailability or `no_usable_safety_fact`.
- Those reports carried usable false-risk facts but omitted some optional risk
  fields, so the truthful status remained UNKNOWN while the existing policy's
  `allow` result was true. Seven cohort receipts reached
  `BUY_AUTHORIZED_UNKNOWN`; the position ledger confirms all 31 admitted arms
  projected.
- The first observed request completed from `WAIT_SECURITY` to checked in about
  3.2 seconds; later requests completed in about 1.7-2.3 seconds, inside the
  unchanged execution deadline.

This is sufficient evidence that the missing Robinhood enrichment route was a
real causal break and is now exercised. It is not yet a mature profitability or
steady-state projection-rate result.

Observe at least 30 minutes and enough admitted Robinhood arms. Count explicit
report, missing-report and network-error receipts separately. The target is to
reduce Robinhood UNKNOWN/expiry from 46/61 (75.4%) toward 25% or below and raise
projected/admitted above 50%, without converting missing data to PASS. BSC and
Solana projection rates, held/exit latency and HTTP cadence must not regress.
