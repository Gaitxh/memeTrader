# Future Live Signer, Transaction Verifier and Release Specification

Date: 2026-09-04
Status: `FUTURE DESIGN ONLY / LIVE REMAINS LOCKED / NOT IN GATES A-C`

## 1. Objective

Use the same StrategyDecision/Allocation/OrderIntent/ExecutionPlan lifecycle for Paper and future Live while isolating private keys and preventing an Agent, Web page, provider response or compromised route builder from authorizing arbitrary transactions.

No current document, test, Web control or strategy result enables Live. A separate reviewed implementation and explicit user authorization are required.

## 2. Separation of responsibilities

### Runtime/strategy process

- creates immutable OrderIntent;
- requests/builds a current amount-specific transaction plan;
- validates expected economics/timing/risk;
- never stores a private key;
- submits a verified signing request only after all gates;
- records send/confirmation/reconciliation.

### Transaction verifier

- independently decodes/resolves the full transaction/message and address lookup tables;
- proves it matches the immutable OrderIntent/ExecutionPlan;
- rejects unknown/disallowed instructions/accounts/programs/value changes;
- emits a verification hash/result.

### Signer

- isolated local/hardware/OS-protected component;
- accepts only an allowlisted, recently verified plan hash/request;
- enforces independent chain/account/notional/rate/risk limits;
- signs but does not choose strategy/route;
- returns a signature/signed payload through a bounded channel;
- has no Agent/Web/project-write authority.

### Sender/reconciler

- broadcasts through allowlisted RPC/provider;
- records attempt before side effect;
- tracks signature/nonce/blockhash/receipt;
- reconciles actual token/native balance and fee deltas;
- never blind-resends an ambiguous attempt.

These may share a host initially but remain separate modules/process/security boundaries.

## 3. Key material

Private key/seed must not exist in:

- `config.json`;
- SQLite;
- logs/notifications/Web/API;
- Agent prompts/results;
- Common Space/C2C/Git;
- test fixtures;
- arbitrary environment dumps.

Preferred options, subject to platform review:

- hardware wallet/secure device for manual/capped phase;
- OS-protected local signer/credential store;
- dedicated low-capital hot wallet in a separately permissioned signer service.

A key previously pasted/exposed is never used. Wallet funding is limited to the reviewed risk budget.

## 4. Chain identity

Before signing/sending:

- exact chain/network/genesis or chain ID verified;
- allowlisted RPC endpoints/version;
- fee payer/signer public key exact;
- recent blockhash/nonce current;
- transaction expiry/deadline known;
- quote/build context not stale;
- address lookup tables resolved at current state;
- no testnet/devnet/mainnet ambiguity.

Wrong chain/network triggers a chain/global Live-send breaker.

## 5. Transaction-plan verification

The verifier checks the complete decoded message against the plan:

- purpose: BUY/SELL/APPROVAL/ACCOUNT_CREATE/other explicitly allowed;
- exact input/output mint and raw amount/maximum spend;
- exact expected destination/associated token account;
- minimum output/slippage bound;
- allowlisted router/program IDs and verified spender/Permit2 where applicable;
- fee payer/signers/writable accounts;
- native-value transfers;
- token transfer/approve/close/set-authority/mint/burn instructions;
- compute budget/priority fee/tip limits;
- platform/referral fee recipient/amount;
- account creation/rent;
- no unknown instruction/program/account side effect;
- plan/intent/idempotency/version hashes;
- current simulation result.

Address lookup tables/inner instructions are resolved enough to enforce these conditions; encoded/opaque provider output is never signed blindly.

## 6. Explicitly disallowed by default

- SystemProgram transfer to an unrelated address;
- setAuthority/owner/close-authority changes;
- unlimited EVM approvals unless a separately reviewed exact spender/policy permits them;
- arbitrary delegate/permanent-delegate/transfer-hook interaction outside the verified route;
- wallet drain/close-account/withdraw instructions;
- unknown program/router/spender;
- transaction whose decoded amount/mint/minimum output differs from the intent;
- stale quote/blockhash/deadline;
- a transaction supplied by an Agent/browser/user URL;
- signing when a global/chain/strategy/position breaker blocks the action.

Necessary associated-account creation or wrap/unwrap instructions require exact allowlisted semantics and cost bounds.

## 7. Independent signer policy

The signer rechecks:

- verification result/hash freshness;
- chain/account/action;
- maximum per-order spend/proceeds tolerance;
- maximum daily new exposure/loss;
- maximum open physical positions/cluster exposure;
- minimum cash/gas reserve;
- no unresolved critical/ambiguous transaction;
- rate limit/cooldown;
- local operator Live-enable lease/expiry;
- emergency pause.

The signer cannot be persuaded by model text or StrategyDecision reason. It signs only structured verified plans.

## 8. Simulation

Before send, use current maintained chain simulation/build semantics:

- complete transaction/message;
- exact fee payer/account state;
- current block/context;
- compute/gas/fee estimate;
- token balances/transfer restrictions;
- min-output and program errors;
- logs/inner instructions when available.

Simulation success is not a fill guarantee. Simulation incomplete/unknown blocks initial Live release unless explicitly reviewed in a later version.

## 9. Attempt and idempotency

Before signing/send:

- immutable Live ExecutionAttempt with exact intent/plan/verification hash and state `PREPARED`;
- signed request/result appended;
- send result appended;
- unique idempotency key prevents a second logical order;
- Solana signature or EVM nonce/transaction hash bound to the attempt.

If status is ambiguous, enter `UNKNOWN_SUBMITTED/RECONCILIATION_REQUIRED`. Do not regenerate/resend merely because the local call timed out.

## 10. Confirmation and reconciliation

### Solana

- signature send/received;
- configured commitment/finality;
- block/slot/error;
- actual pre/post token/native balances and fees;
- route/transfer result versus expected;
- partial/failure/expired states.

### EVM

- nonce/send/hash;
- mempool/dropped/replaced/reorged/receipt status;
- actual logs/balance deltas;
- gas/L1/approval/token-tax effects;
- replacement/cancellation lineage.

Only reconciled deltas create `LIVE_RECONCILED` Fill/PositionEvent/account cash. A transaction hash alone is not a final fill.

## 11. Ambiguous/failure states

- `PREPARED_NOT_SIGNED`;
- `SIGNED_NOT_SENT`;
- `SEND_ERROR_KNOWN_NOT_SUBMITTED`;
- `UNKNOWN_SUBMITTED`;
- `SUBMITTED_PENDING`;
- `DROPPED/EXPIRED`;
- `FAILED_CONFIRMED`;
- `CONFIRMED_RECONCILIATION_MISMATCH`;
- `REORGED/REPLACED`;
- `RECONCILED_FILL`.

Each has explicit retry/rebuild/reconcile rules. Unknown submission activates the Live-send breaker.

## 12. Physical portfolio

Future Live allocations across virtual strategies are not copied one-for-one. PortfolioAllocator creates one physical intent per exact token/direction/decision time/risk state:

- combines supporting policy signals without adding virtual cash;
- computes one physical amount under account/capacity/cluster/tail limits;
- requests a new exact-aggregate plan;
- tracks attribution separately from physical PNL;
- prevents simultaneous contradictory buy/sell orders.

A 20 USDC virtual quote is never reused for a larger physical amount.

## 13. Initial release ladder

### Phase 0 — Paper only

Current v5 work. No signing/send.

### Phase 1 — verifier/offline fixture

Decode known benign/malicious/test transactions; no wallet.

### Phase 2 — Devnet/test chain

Dedicated test wallet, tiny self/route transactions, signatures/receipts/reconciliation.

### Phase 3 — Mainnet quote/build/simulate shadow

Real current plans and simulation for tiny declared amounts, no signing/send.

### Phase 4 — manual-sign canary

Explicit per-order user confirmation/hardware signer; tiny capital; one order at a time; full reconciliation; automatic strategies do not send.

### Phase 5 — capped autonomous canary

Separate explicit authorization, short Live-enable lease, tiny per-order/day/open-position limits, only the mature reviewed policy/chain/venue.

### Phase 6 — scale review

Only after many reconciled live outcomes, operational incidents, tail/cost/landing evidence and explicit new risk approval.

No phase advances automatically.

## 14. Release gates

- mature forward Paper policy under common cost/tail/robustness criteria;
- current execution adapter/build/simulation completeness;
- independent transaction verifier tests/red-team fixtures;
- isolated signer/key review;
- attempt/idempotency/unknown-send recovery;
- balance/fee reconciliation;
- circuit breakers/alerts/manual pause;
- wallet funding and worst-case loss budget;
- no secret exposure;
- explicit user authorization for the exact phase.

A profitable Paper curve alone is insufficient.

## 15. Web/Agent boundary

Public/read-only Web:

- never exposes full wallet address/key/signed payload/calldata/raw transaction beyond safe masked/allowlisted fields;
- cannot enable Live, sign, send or release breakers;
- shows Live locked/phase/last reconciled state.

Local privileged UI may later request a manual Paper action or display a transaction for review. Live enable/approve must use a separate authenticated local process/physical confirmation and append immutable authorization. Agent outputs have no signer/sender tool.

## 16. Notifications

Highest priority:

- unknown submitted transaction;
- confirmation/reconciliation mismatch;
- unexpected token/native balance change;
- wrong chain/program/verifier rejection;
- signer unavailable/limit rejection;
- critical exit unable to send/land;
- daily/tail limit/breaker.

Never include secret material or raw signed transaction in notifications.

## 17. Tests/red team

- malicious provider response adds unknown transfer/program -> verifier rejects;
- mint/amount/min output differs -> rejects;
- stale blockhash/quote -> rejects;
- address lookup table resolves to disallowed account -> rejects;
- setAuthority/close account/unrelated transfer -> rejects;
- EVM spender/approval mismatch -> rejects;
- signer cannot sign without exact verification hash and active lease;
- duplicate timeout cannot produce duplicate send/fill;
- unknown submission blocks new sends until reconciliation;
- confirmed failure accounts for fee but no acquired asset;
- actual balance delta mismatch triggers breaker;
- virtual account total cannot become physical amount;
- Web/Agent/config cannot access key or enable Live;
- old Paper/Live phases/versions remain immutable.

## 18. Current conclusion

Design the shared lifecycle now, but do not add a Mainnet signer/broker in Gates A-C. The first Live-related code worthy of development after Paper maturity is the transaction verifier and full build/simulation/reconciliation shadow—not a private-key field or a Web toggle.
