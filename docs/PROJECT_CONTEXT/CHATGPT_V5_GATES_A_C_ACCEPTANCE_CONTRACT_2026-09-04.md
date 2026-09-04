# V5 Gates A–C Minimal Implementation and Acceptance Contract

Date: 2026-09-04
Status: `CURRENT CODEX RELEASE CONTRACT / SUPERSEDES BROADER WORDING FOR THE FIRST DIFF`

## 1. Scope

The first coherent v5 code release contains only:

- Gate A: current premise/authority/r6 verification;
- Gate B: atomic v4 new-entry stop frontier plus v5 registry/readiness;
- Gate C: minimal shared execution-observation and virtual-Paper event lifecycle, deployed idle/no active executable policy.

It does not implement Launch Recall activation, Fast Exit parameters, PumpSwap flow, PeakGuard, Agent treatment, Reawakening, full cockpit, BSC/Robinhood, signer or Live.

Existing v4 positions/marks/quotes/held-account risk/SELL/writeoff continue unchanged.

## 2. Gate A — premise table

Codex returns one table with `VERIFIED / REVISE / SUPERSEDED` and exact evidence for:

| Premise | Evidence required |
|---|---|
| current v4 definition/version | registration row and definition hash/version |
| v4 stages are cumulative historical policies | current `chain_meme_trader_policies()`/definition entry gates |
| v4 entry source/frontier unit | exact upstream table/id and enrollment predicate |
| existing v4 open/terminal positions | counts/status without changing rows |
| current v4 exit/runtime paths | methods/loops that must remain active |
| existing route/surface/mint/held-account facts | reusable method/table versions |
| existing generic lifecycle schema | exact reusable entities or explicit absence |
| current Codex/thread/worktree state | one writer; changed files/collision check |
| current Live state | `live.enabled=false`/locked, no signer/send |

Any disproved premise modifies the implementation plan before editing. No historical report overrides current bytes/SQLite.

## 3. Gate B — authority entities

### Required behavior

- v4 registration/rows remain immutable;
- append a separate immutable entry-stop/supersession frontier for v4;
- register one v5 epoch and 12 immutable policy definitions/readiness states;
- write v5 registry + v4 stop frontier atomically;
- v4 enrollment honors the exact upstream ID frontier;
- existing v4 exit/valuation/held monitoring ignores the entry stop and continues;
- v5 entry families remain non-executable after Gates A-C.

### V5 policy readiness after Gate B

- Launch Fast: `pending_execution_kernel_or_activation`;
- Launch Balanced: same;
- Launch Peak: `advisory_control/feature_pending`;
- Launch Agent: `advisory_control/treatment_inactive`;
- Flow policies: `feature_pending/shadow_only`;
- Reawakening policies: `baseline_building`;
- every policy `live_eligibility=false`.

Names may match local conventions, but their semantics must be machine-readable.

### Atomicity invariant

After transaction failure, either:

- neither v5 registry nor v4 stop frontier exists; or
- both exist and reference each other/frontiers consistently.

Never stop v4 entries without a durable v5 registry, and never register v5 while v4 has no deterministic stop boundary.

## 4. Gate C — minimal lifecycle entities

Codex may reuse existing schemas where semantics are exact. Otherwise add the smallest v5-isolated entities necessary to represent:

1. `Opportunity/CohortReference` — current/forward source lineage, no backfill;
2. `StrategyDecision` — policy/version/frame/evidence/available-at/status/reason;
3. `VirtualAllocation` — independent strategy account, selected/not selected, 20 USDC requested/selected amount, readiness/capital/capacity reason;
4. `ExecutionObservationAttempt` — persisted before Jupiter/provider call;
5. `ExecutionObservationResult` with evidence class:
   - `ENTRY_BUY_QUOTE`;
   - `SAME_STATE_REVERSE_SELLABILITY_PROBE` and `state_relation=same_pre_buy_state`;
6. `VirtualPaperFill` — simulated per selected virtual allocation, references one exact-identical shared observation; conservative and central views separated;
7. `PositionEvent`/minimal reconstructable projection — OPEN/REDUCE/CLOSE/WRITEOFF foundations or an explicit bridge to current v4 exit machinery.

Gate C may remain idle in production. Deterministic tests exercise fills/events. A research-only natural observer may persist observation/no-fill rows if separately identified, but cannot mutate v5 cash/positions.

## 5. Critical semantic separations

### Shared observation versus virtual fill versus future physical order

- one 20 USDC provider observation may support N exact-identical virtual allocations;
- each independent virtual account receives an explicitly simulated fill/event referencing that observation;
- virtual cash/PNL is never added as physical capital;
- a future aggregate physical amount requires a new exact-amount plan/quote/simulation;
- different amount/time/deadline/surface-policy contract cannot share.

### BUY quote versus reverse probe

- the reverse probe is based on the same pre-BUY state unless a stronger source says otherwise;
- it proves current route/addressability/capacity for the conservative acquired amount;
- it is not a sequential round-trip simulation;
- it cannot create a SELL fill, current position value or realized PNL;
- post-entry valuation/exit requires a later current amount-specific quote.

### Token identity versus market surface

- exact chain/token mint is required;
- surface classification is explicit: exact canonical, exact noncanonical, opaque, unknown, invalid/mismatch;
- invalid/mismatch rejects;
- opaque/unknown may later be bounded Paper exploration only, pool safety unknown, Live false;
- no different pool’s safety/watcher is borrowed;
- Gate C does not activate any of these policy buckets yet.

### Time/order

- source/observed/ingested/recorded/available/requested/completed times remain distinct;
- no response before request;
- no late response as valid current evidence;
- no exact same-slot transaction order invented without a source-provided index;
- ordering quality is explicit when relevant;
- no old source row enters v5 after activation by backfill.

## 6. Minimal cost semantics

- exact 20 USDC input for initial virtual policy comparison;
- BUY central output and minimum output stored separately;
- reverse-probe central/minimum output stored separately;
- minimum BUY output is the conservative virtual acquired amount;
- no second 4% debit after a 400-bps minimum-output threshold;
- route fees embodied in output are not deducted again;
- explicit network/priority/account/other costs carry source/time/completeness;
- unknown cost remains unknown;
- no fill/account mutation on no-route/error/stale/invalid.

## 7. Required targeted tests

Exact names are Codex-owned; each behavior must have a focused test.

### Registration/frontier

1. atomic v5 registry + v4 frontier all-or-none;
2. v4 registration/history unchanged;
3. v4 source ID after frontier cannot create new v4 decision/position;
4. source ID at/before frontier retains prior deterministic behavior;
5. v4 open position still receives mark/quote/SELL/writeoff after frontier;
6. v5 cannot enroll source at/before family frontier;
7. all 12 definitions/readiness are immutable/machine-readable;
8. Runtime restart registration is idempotent.

### Lifecycle

9. StrategyDecision cannot directly write Trade/Position;
10. observation attempt is durable before provider call;
11. same idempotency key cannot duplicate observation/fill/event;
12. exact-identical 20 USDC virtual allocations share one provider observation;
13. each virtual account gets its own simulated allocation/fill/account event;
14. different amount/time/surface contract does not share;
15. no-route/error/stale produces no fill/cash mutation;
16. conservative minimum and central estimate remain separate;
17. reverse probe tagged same-pre-BUY-state and cannot become SELL fill/value;
18. position projection rebuilds from events or bridge invariant is exact;
19. interrupted attempt recovers without duplicate fill;
20. policy not ready at entry cannot be attached retroactively.

### Safety/UI/non-regression

21. opaque/unknown surface is not labeled safe/Live eligible;
22. v4 Web calls it historical cumulative evolution, not global same-entry comparison;
23. v5 shows registered/readiness, no fabricated rank/trade;
24. v4 legacy open positions remain visible/operational separately;
25. browser/API request cannot cause Jupiter/RPC/Agent/broker work;
26. Live remains locked; no signer/key/send path added.

## 8. Release validation

At the coherent release boundary:

- closest targeted tests pass;
- Python compile passes for changed source/tests;
- current schema/version/frontier rows queried;
- no v4 post-frontier new entry in deterministic test/observation;
- one controlled Runtime restart only;
- scheduled Paper Runtime/single instance/SQLite/WAL/ports/health checked according to current project rules;
- existing v4 exits/held monitoring remain active;
- v5 registry shown idle/readiness-only;
- no natural executable v5 trade is required or manufactured;
- Live false/locked.

Full suite is appropriate only once the coherent Gates A-C release is complete, not after every local edit.

## 9. Codex RESULT contract

Return:

- current premise table;
- exact changed files/methods/tables;
- v4 original registration/version/hash and stop frontier;
- v5 epoch/policy version/hash/readiness;
- schema/lifecycle sharing/idempotency design;
- tests and results;
- controlled deployment/runtime evidence;
- v4 exit non-regression;
- any concrete blocker/revision;
- no profitability/active-v5/Live claim.

Do not continue to Gate D until Lead acknowledges this RESULT.

## 10. Stop condition

Gates A-C are complete when the authority boundary and minimal lifecycle are implemented, tested and deployed idle without disrupting v4 exits. Strategy activation/trading volume belongs to Gate D.
