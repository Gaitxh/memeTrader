# Pons economics FIFO repair 178 (2026-09-15)

## Diagnosis

- Stage 177's final Pons V2 slot discovered six new Robinhood contracts. All six
  entered identity hydration, but all were `no_pair`: they were `TokenLaunched`
  bonding-curve events with no graduated DEX pool, so the ordinary DEX strategy path
  correctly did not manufacture a snapshot or trade.
- The separate curve-economics queue had enrolled 3,340 launches but recorded 1,977
  `EXPIRED_UNATTEMPTED` and 253 `DEFERRED_CAPACITY` outcomes. It consumed only the
  FIFO head per once-per-five-turn economics slot.
- At the frozen production frontier there were 23 pending rows. The first five used
  the native zero-address quote, which the model always rejects locally as
  `UNSUPPORTED_QUOTE_NATIVE_ETH_USD_NOT_PROVEN` before any HTTP/RPC call. A potentially
  verifiable ERC20 quote was behind them. Thus zero-request terminal cases consumed
  the only scarce observer slots and starved higher-information cases.
- An independent read-only Agent confirmed the same root cause and the relevant
  held-priority, append-only receipt, and one-network-attempt constraints.

## Change

- Added one canonical local unsupported-quote receipt shared by the queue fast path
  and `PonsEconomicsObserver.observe()` so their status/reason/provenance cannot drift.
- When held work is idle, one economics step may terminalize up to the existing
  32-row queue capacity of consecutive native-zero quotes without network access.
  It then permits at most one remaining observer call, preserving the previous
  maximum network-attempt cadence.
- When held work is busy, the step does not pop even locally decidable rows. Expiry,
  FIFO order for all non-native cases, 15-minute TTL, queue capacity, and retry
  behavior are unchanged.
- Each locally terminalized row is returned to Runtime and persisted as append-only
  `native_curve_economics` evidence. `attempted` counts only real observer calls;
  `locally_terminalized` exposes the new deterministic path.
- Results remain `decision_eligible=false` and `affects=none`. This does not turn a
  curve estimate, missing DEX pool, unsupported quote, or upstream failure into a
  Paper buy signal. Live remains disabled.

## Verification and deployment

- Focused regression passed 17 tests:
  `pytest tests/test_pons_economics.py tests/test_native_observer_runtime.py
  tests/test_pons_v2_53.py -q`.
- The mixed-queue regression uses five native-zero rows followed by one ERC20 row.
  A busy step changes nothing; the next idle step returns six receipts but calls the
  observer exactly once for the ERC20.
- Natural production evidence on PID 77968 at 15:15:08Z matched the test: pending
  fell from 23 to 17, five native rows received local unsupported receipts,
  `locally_terminalized` became 5, and `attempted` rose only 1 (1,340 to 1,341).
  The now-reachable ERC20 attempt received Blockscout HTTP 403 and therefore remained
  truthfully `UNKNOWN`; no safety or trading authority was inferred.
- The runtime manifest previously omitted `pons_economics.py`; it now hashes that
  affected module. Final manual restart PID 78876 began at
  2026-09-15T15:15:41Z and matched disk hashes for both `runtime.py` and
  `pons_economics.py`.
- `/health`, `/api/live`, and `/api/performance` returned 200. Funding remained
  `chain-meme-trader/funding-20260906-v002-final-1000`, Paper remained true, and Live
  remained locked. No account initialization or schedule was created.

## Next manual review

On the next user-triggered supervision run, measure post-activation pending depth,
`EXPIRED_UNATTEMPTED`, `DEFERRED_CAPACITY`, `locally_terminalized`, real `attempted`,
and ERC20 outcome reasons. The repair succeeds if expiry/capacity loss falls and
eligible ERC20 latency improves without increasing observer attempts per economics
slot or regressing held/exit latency. A separately reviewed, strictly forward Paper
curve strategy would still require verified USD conversion, exact curve code/state,
amount-specific buy and sell modeling, and explicit fast-exit safety; this queue fix
does not grant that authority.

