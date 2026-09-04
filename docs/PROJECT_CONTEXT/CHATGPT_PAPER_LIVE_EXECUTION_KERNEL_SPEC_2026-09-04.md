# Shared Paper/Live Execution Kernel Specification

Date: 2026-09-04
Status: `P0 DESIGN / PAPER IMPLEMENTATION FIRST / LIVE LOCKED`

## 1. Design objective

Paper and future Live execution use the same intent, plan, attempt, fill, position and reconciliation schema. They differ only in the execution adapter and authority.

Current v5 implementation scope ends at `PaperExecutionAdapter`. No private key, signer, mainnet send or Live switch is authorized.

The architecture must make it possible to add a separately reviewed Live adapter without rewriting strategy logic or pretending quote-only Paper results are real fills.

## 2. Separation of responsibilities

### Strategy layer

Produces:

- immutable StrategyDecision;
- desired side/notional or raw amount;
- urgency/deadline;
- reason/policy version;
- exact available MarketFrame/evidence references.

It does not call Jupiter, sign, send, mutate cash or create a Trade directly.

### Portfolio layer

Produces:

- selected/rejected allocation;
- available capital and cluster/capacity checks;
- one physical target intent from potentially many virtual strategy allocations;
- deterministic allocation rule.

It does not fabricate a fill.

### Execution planner

Produces:

- amount-specific route/quote;
- central output/minimum output;
- route legs and holding-surface relationship;
- cost and expiry fields;
- simulation/build requirements;
- immutable ExecutionPlan.

### Execution adapter

Consumes a valid plan and records an attempt before any side effect.

- Paper: no signing/broadcast, converts a current valid plan to clearly labeled simulated fill semantics;
- future Live: isolated signing, send, confirm and reconcile under separate authority.

### Position projector

Consumes immutable fills/writeoffs/adjustments to construct current position/cash projections. A projection can be rebuilt; source events cannot be overwritten.

## 3. Core entities

### 3.1 `strategy_decisions`

Minimum fields:

- id;
- strategy/version/registration;
- cohort/opportunity/frame IDs;
- token/surface;
- side;
- requested virtual amount;
- status/reason;
- decision/available timestamps;
- feature/evidence digest;
- Paper role and Live eligibility.

Immutable.

### 3.2 `portfolio_allocations`

- decision ID;
- virtual account;
- selected amount;
- selection status/reason;
- portfolio snapshot/version;
- cluster and capacity facts available at selection;
- allocation timestamp.

Immutable selection result. A later release/cancel is a new event.

### 3.3 `order_intents`

- id and unique idempotency key;
- execution mode (`paper`, future `live`);
- chain, side, input/output mint;
- desired exact raw input or exact target notional;
- token/surface/opportunity;
- urgency/tier/deadline;
- reason and source decision/exit event;
- supporting allocation IDs;
- created/available time;
- state.

Idempotency-key candidate:

`hash(mode, execution_policy_version, opportunity_or_position_id, side, tranche_index, exact_input_amount, reason_event_id)`

Do not include mutable wall-clock noise merely to bypass deduplication.

### 3.4 `execution_plans`

- intent ID and plan version;
- provider/router;
- requested/completed/context slot/times;
- exact input amount;
- central output;
- minimum output/threshold;
- slippage mode/bps;
- price impact;
- normalized route legs;
- holding-surface relationship/verifiability;
- quote expiry and blockhash expiry when built;
- network/priority/tip/token/account-creation fee fields;
- cost-completeness status;
- simulation/build status;
- raw sensitive payload reference stored outside Web allowlist;
- terminal status/error classification.

Plans are immutable. Refreshing creates a new plan linked to the prior one.

### 3.5 `execution_attempts`

Write before provider/broker/signing activity:

- intent/plan/adapter;
- attempt number/idempotency key;
- requested time;
- state;
- external stable identifiers where safe;
- previous uncertain-attempt relationship;
- completed time/error class.

Never retry an ambiguous Live send until reconciliation determines whether it landed.

### 3.6 `fills`

- intent/plan/attempt;
- mode and fill semantics;
- chain signature for future Live;
- input spent/output received raw amounts;
- minimum/central/live-reconciled classification;
- explicit network/priority/tip/rent/token fees;
- total known cost and completeness;
- effective price;
- slot/block/confirmed/finalized/reconciled times;
- partial/full status;
- balance-delta evidence;
- created time.

A Paper fill has no transaction signature and is never labeled confirmed/reconciled.

### 3.7 `position_events`

- `OPEN`, `INCREASE`, `REDUCE`, `CLOSE`, `WRITEOFF`, future `RECONCILIATION_ADJUSTMENT`;
- position/allocation/fill linkage;
- token/raw amount and cost/proceeds deltas;
- strategy/physical attribution;
- reason and event time.

Current position is a projection from these immutable events.

## 4. State machines

### Intent

`CREATED -> PLANNING -> PLANNED -> ATTEMPTING -> FILLED`

Alternative terminals:

- `NOT_SELECTED` lives before intent;
- `NO_ROUTE`;
- `QUOTE_EXPIRED`;
- `PLAN_INVALID`;
- `SIMULATION_REJECTED`;
- `CANCELLED_BEFORE_SIDE_EFFECT`;
- `ERROR_RETRYABLE`;
- `ERROR_TERMINAL`;
- future `SEND_AMBIGUOUS`;
- future `CONFIRMATION_TIMEOUT`;
- future `RECONCILIATION_FAILED`.

Transitions are append-only events or compare-and-swap projections. No state may jump from Decision to Fill without plan/attempt.

### Position exit

`OPEN -> WATCH -> EXIT_ARMED -> EXIT_INTENT -> EXIT_ATTEMPT -> PARTIALLY_REDUCED / CLOSED`

Orthogonal/terminal:

- `DATA_STALE`;
- `EXACT_ACCOUNT_ALERT`;
- `DEAD_TERMINAL`;
- `WRITTEN_OFF`.

## 5. Planning and freshness

An intent is planned only from facts available at planning time. Validate:

- exact input/output mint and chain;
- remaining/current raw amount for SELL;
- quote response not before request;
- quote total/queue age within the registered version;
- route/holding-surface classification required by that policy;
- minimum output and central output positive/parseable;
- no terminal no-reentry/no-exit contradiction;
- all cost-completeness fields labeled.

If a plan expires before attempt, append `QUOTE_EXPIRED` and create a new plan under the same intent when policy/deadline permits. Do not update the old response.

## 6. Paper adapter semantics

Paper uses the real current amount-specific plan and the same queue/provider latency. It does not sign or broadcast.

Record at least two outcome views:

### Conservative Paper fill

- BUY received amount = valid minimum output threshold;
- SELL proceeds = valid minimum output threshold;
- subtract only separately known costs not already embedded in the route/output;
- missing costs keep `cost_completeness != complete`.

This is the account-authoritative first v5 Paper view.

### Central quote estimate

- uses central quoted output;
- independently labeled non-guaranteed estimate;
- never mixed into conservative cash ledger.

Optional later slippage/landing model must be separately registered and trained only on future Live-reconciled or valid external execution evidence. It cannot retrospectively rewrite Paper fills.

Paper no-route/error/stale remains no fill. A DEX mark cannot substitute.

## 7. Exact acquired quantity and exits

The conservative BUY minimum output becomes the Paper position’s acquired raw quantity. Every full/partial exit requests a quote for the actual remaining/specified raw amount.

Do not:

- sell the central BUY output after booking the minimum BUY output;
- proportionally scale a full-size quote for a partial exit when nonlinear impact matters;
- use initial quantity after prior partial exits;
- reuse a quote from another strategy amount/time/surface.

One shared entry fill may create several virtual allocations only when their amount/time/cost contract is identical. Otherwise plan independently.

## 8. Error taxonomy

Normalize provider/adapter errors without discarding raw internal diagnostics:

- `NO_ROUTE`;
- `RATE_LIMITED`;
- `TRANSPORT_TIMEOUT`;
- `CONNECTION_ERROR`;
- `PROTOCOL_INVALID`;
- `RESPONSE_LATE`;
- `AMOUNT_INVALID`;
- `TOKEN_TRANSFER_IMPOSSIBLE`;
- `SIMULATION_REVERTED`;
- `ALLOWANCE_MISSING` (EVM planning state, not necessarily terminal);
- `INSUFFICIENT_BALANCE`;
- `BLOCKHASH_EXPIRED`;
- future `SEND_AMBIGUOUS`;
- future `CONFIRMATION_TIMEOUT`;
- future `BALANCE_MISMATCH`;
- `UNKNOWN_ERROR`.

A provider’s HTTP status/text maps deterministically. Historical rows are not reclassified in place when a mapping improves; a new parser/version applies forward.

## 9. Retry policy

Retry is policy/urgency specific:

- exact-account emergency: immediate highest-priority attempt, terminal semantics as already frozen;
- armed exit transient error: short bounded retry while deadline/open position remains;
- ordinary no-route: registered backoff;
- stale plan: replan rather than retry the same plan;
- entry: do not chase indefinitely after its opportunity deadline;
- ambiguous future Live send: reconcile first, never blind resend.

Persist next eligible time and attempt count. Fair scheduling prevents one failing position from monopolizing all requests.

## 10. Cost accounting

Separate:

- AMM/router fees already reflected in route output;
- adverse slippage/minimum-output semantics;
- explicit platform fee;
- Solana base/priority fee;
- Jito tip if future adapter;
- token-account/rent cost when applicable;
- EVM gas and L1 data fee;
- transfer/tax amount;
- unobserved MEV/landing uncertainty.

Do not double deduct route fees/slippage already embodied in output. `cost_completeness` values:

- `route_output_only`;
- `network_estimated`;
- `simulation_complete_estimate`;
- future `live_reconciled`;
- `unknown/incomplete`.

Account reports show PNL together with its cost layer.

## 11. Future Live adapter authority boundary

Not implemented in this cycle. Required design when reviewed:

### Isolated signer

- separate process/device with no Agent/Web access;
- private key never leaves signer;
- narrow local authenticated interface;
- validates chain/cluster, allowed programs/routers, input/output mint, maximum amount, min output, fee/tip, expiry, fee payer and allowed instruction set;
- rejects arbitrary extra instructions/account drains;
- returns only signature/signed transaction needed by sender.

### Release controls

- explicit strategy/live version allowlist;
- small-capital/daily/tail limits;
- no new entries when emergency exit/reconciliation unresolved;
- append-only local command and release audit;
- public Web read-only;
- Live cannot be enabled by Agent, browser extension or remote unauthenticated request.

### Simulation/send/confirmation/reconciliation

1. build current transaction;
2. validate decoded instructions locally;
3. simulate at current block/context;
4. sign through isolated signer;
5. write attempt before send;
6. broadcast under registered adapter;
7. confirm/finalize under explicit commitment;
8. reconcile pre/post balances and fees;
9. only reconciled deltas create Live Fill/PositionEvent;
10. uncertain sends enter reconciliation, not immediate retry.

## 12. Emergency Live execution considerations

A future emergency policy may use:

- wider registered slippage;
- alternate supported routes;
- higher priority fee/tip;
- partial tranches when full-size route fails.

These are explicit policy versions, not ad hoc runtime behavior. They cannot bypass instruction/signer allowlists or spend beyond the remaining position/risk budget.

## 13. Multi-chain adapter interface

Common adapter methods:

- `quote(intent) -> immutable plan`;
- `build(plan) -> build result`;
- `simulate(build) -> simulation result`;
- `attempt(plan/build) -> attempt`;
- future `send(signed) -> submission result`;
- future `confirm(id) -> confirmation`;
- future `reconcile(id, expected) -> fill/balance result`.

Solana/Jupiter and EVM/0x implement chain-specific details without changing StrategyDecision/OrderIntent/Fill/PositionEvent semantics.

## 14. Reconciliation invariants

- cash/token balances derive from immutable fills, not Decision labels;
- total input/output allocation never exceeds physical reconciled fill;
- virtual Paper allocations are explicitly simulated and never added to physical assets;
- full close cannot leave positive raw balance projection unless a reconciliation adjustment explains it;
- writeoff does not claim tokens disappeared; it recognizes zero economic recovery under the terminal policy;
- duplicate signature/attempt cannot double-book a fill;
- strategy/account snapshots are reproducible.

## 15. Security and Web exposure

Web/API allowlists may expose:

- intent/plan/attempt/fill IDs;
- safe route summary;
- amounts, times, statuses and cost completeness;
- public transaction signature after future send;
- masked/public addresses as explicitly allowed.

Never expose:

- private key/seed;
- signer token/session;
- raw secret headers;
- unrestricted unsigned/signed transaction payloads on public endpoints;
- internal provider API keys;
- wallet-wide unrelated assets/history.

## 16. P0 implementation boundary

Implement now:

- immutable tables/events for StrategyDecision, allocation, OrderIntent, Plan/Attempt, Paper Fill and PositionEvent;
- Paper adapter using current exact Jupiter amount/minimum-output semantics;
- v4 entry-stop and v5 natural forward registration;
- shared plan/fill for exact-identical virtual allocations;
- exit-first scheduling and retry classification;
- restart/idempotency and projection tests;
- read-only Web lineage.

Do not implement now:

- signer;
- Mainnet send;
- Jito transaction path;
- automatic Live enablement;
- EVM transaction broadcast;
- an opaque learned slippage model;
- historical conversion/backfill of v4 rows.

## 17. Acceptance tests

- StrategyDecision cannot directly create a trade/position;
- attempt exists before provider adapter call;
- same idempotency key cannot duplicate intent/attempt/fill;
- stale plan creates a new linked plan and never mutates old;
- exact-identical allocations share one fill, different contracts do not;
- conservative and central Paper outcomes remain separate;
- no-route/error produces no fill/cash mutation;
- partial exit uses the exact remaining/partial raw amount;
- restart resolves incomplete Paper planning without duplicate fill;
- critical exit has scheduling priority;
- account/position projections rebuild from events;
- all current Live surfaces remain locked and no signer/key is introduced.
