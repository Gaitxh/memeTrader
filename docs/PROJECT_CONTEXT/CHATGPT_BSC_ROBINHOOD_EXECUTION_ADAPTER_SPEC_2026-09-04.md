# BSC and Robinhood Chain Execution Adapter Specification

Date: 2026-09-04
Status: `P3 RESEARCH DESIGN / AFTER SHARED KERNEL / NO EVM PAPER OR LIVE CLAIM YET`

## 1. Shared versus chain-specific

Reuse across chains:

- StrategyDecision;
- PortfolioAllocation;
- OrderIntent;
- ExecutionPlan/Attempt/Fill;
- PositionEvent/projection;
- idempotency, clocks, no-fill/error taxonomy;
- strict-forward registration and promotion lifecycle;
- Web truth layers.

Do not reuse blindly:

- gas/native asset/L1 fee assumptions;
- router/allowance/Permit2 behavior;
- token transfer/tax/blacklist semantics;
- pool/LP/custody program models;
- confirmation/finality policy;
- asset universe/classification;
- MEV/private-order path;
- cost maturity.

Each chain/adapter has its own immutable execution/safety/cost version.

## 2. EVM common exact lifecycle

For each candidate amount:

1. exact chain ID/token address/decimals and quote asset;
2. amount-specific firm BUY quote/route for a declared taker;
3. build transaction fields and allowance/spender requirements;
4. current-block simulation/validation;
5. use conservative expected acquired token amount for immediate SELL quote;
6. amount-specific SELL route/build/simulation;
7. record gas, network/L1 data, token taxes, protocol fees, minimum output and failure semantics;
8. classify `executable_paper`, `research_only`, or invalid;
9. no fill/account PNL until the chain-specific Paper version is registered.

BUY and SELL observations need separate block/request/response clocks. “Same time” is bounded asynchronous evidence, not falsely called one atomic block when it is not.

## 3. 0x integration semantics

Use current official supported-chain/Swap API endpoints and response schema. Preserve:

- endpoint/API version;
- chain ID;
- taker;
- input/output token and exact raw amount;
- central/minimum output;
- route/fills;
- gas/gas price/total network fee when supplied;
- fees and token-tax fields;
- allowance target/issues and balance issues;
- simulation status/incomplete flag;
- block/context/request/response clocks;
- terminal error/status.

`/price` or indicative response remains research-only. A firm `/quote`/transaction plan plus simulation is still not an on-chain fill. No API key or calldata/raw transaction is exposed through public Web.

If 0x lacks a route, preserve `no_route`; do not silently substitute a DEX screen price. A later alternate maintained router is a new adapter/source version.

## 4. Taker and allowance

An executable simulation depends on a realistic taker/account state.

Paper options, in order of truth:

1. dedicated public observation/taker address with known state but no private key in Runtime;
2. provider-supported state override/simulation fixture, explicitly labeled;
3. quote/build without valid taker state, labeled `route_only/cost_incomplete`, not executable Paper.

Future Live:

- isolated wallet/signer;
- only approve the exact allowlisted spender returned/verified for the adapter;
- prefer bounded/exact allowance or separately reviewed Permit2 flow;
- approval transaction, gas, delay and residual allowance are part of execution risk/cost;
- do not approve arbitrary router addresses or unlimited amounts by default;
- allowance revocation/expiry policy is explicit.

An allowance problem is not automatically a honeypot, but it blocks current execution until resolved.

## 5. Token transfer and tax semantics

For both chains observe/simulate:

- fee-on-transfer buy/sell tax;
- transfer reversion/blacklist/whitelist;
- max transaction/wallet restrictions;
- cooldown/trading-open rules;
- rebasing/reflection/balance changes;
- proxy/admin/upgradability facts where available;
- actual acquired amount versus quoted expected amount;
- sell of that acquired amount.

Third-party honeypot/risk APIs are cross-check evidence. Current transaction simulation and future reconciled balance deltas are execution truth.

A BUY quote with no realistic SELL simulation/preflight is research-only, not executable Paper.

## 6. BNB Smart Chain adapter

### Network/cost

- chain ID/network version from current official/adapter configuration;
- native gas cost in BNB, converted using a same-time available BNB/USD observation;
- legacy/EIP-1559 fields handled according to current chain/RPC behavior;
- approval + BUY + SELL gas and failure cost;
- no L1 data fee unless the chain/version actually exposes one.

### Market/safety

- broad DEX/launch-token universe can contain fee-on-transfer, blacklist and mutable proxy contracts;
- router simulation and acquired-quantity SELL are mandatory for executable Paper;
- explicit pool/pair/reserve/LP ownership facts when a venue decoder exists;
- noncanonical/opaque routes may remain Paper exploration with Live false.

### MEV

BSC public-mempool sandwich/frontrun risk can make quote-only economics optimistic. Paper cost completeness records the absence of a landing/MEV model. A future private transaction/MEV-protected route is a separate adapter with measured cost/landing behavior.

### Confirmation/reorg

Future Live specifies block confirmation/finality and reorg reconciliation. A transaction hash alone does not create a reconciled fill.

## 7. Robinhood Chain adapter

### Network identity

Use current official Robinhood Chain values, including chain ID 4663 and its Arbitrum/EVM/ETH-gas semantics, with endpoints/version frozen in local non-secret configuration.

### Asset universe exclusion

Before a token can become a Meme cohort:

- fetch/observe the official Stock Token/RWA registry through a versioned append-only observation;
- exact address match excludes/labels `stock_token/rwa`;
- symbol/name similarity alone never classifies;
- registry unavailable/stale is explicit and may block Paper promotion depending on the registered version;
- a later registry update cannot rewrite an earlier decision but applies to future decisions/risk handling as allowed.

### L2/L1 costs

Account for:

- ETH gas;
- L2 execution gas;
- L1 data/posting fee when applicable/observable;
- approval and failed simulation/transaction costs;
- router/protocol/token tax;
- same-time ETH/USD conversion.

A quoted network fee field is validated against simulation/receipt semantics before being called complete.

### Liquidity/route maturity

Robinhood Chain may have thinner/newer liquidity and RWA-focused pools. Preserve no-route, capacity and price-impact distributions. Do not pool its thresholds/outcomes with BSC or Solana.

## 8. Immediate reverse-sell preflight

For each chain:

- BUY minimum/expected acquired raw amount is explicit;
- SELL uses that actual conservative amount;
- if token taxes reduce acquired balance, simulation/reconciliation adjusts the amount rather than pretending the quote quantity arrived;
- BUY and SELL costs are separated and not double-counted in output;
- a successful pool math quote without transfer simulation is not enough;
- recovery ratio/stress/cost completeness become strategy/risk fields.

High-recall Paper may sample poor but positive recovery buckets. No-route/impossible transfer is research-only/invalid, not a fill.

## 9. Paper accounting

Chain-specific Paper fill version declares:

- conservative amount/proceeds semantics;
- whether gas/approval/L1/token taxes are complete, estimated or unknown;
- quote/build/simulation validity window;
- no-route/error/late behavior;
- partial exits and remaining raw balance;
- writeoff terminal.

Do not compare cross-chain PNL without showing different cost completeness. A Solana 4% contract cannot be copied as BSC/Robinhood’s full cost model.

## 10. Held-position monitoring

### BSC

Potential sources:

- new block/log subscriptions or bounded polling;
- exact pair reserve/LP/admin events for supported venues;
- token Transfer/ownership/proxy changes;
- amount-specific route/recovery refresh.

### Robinhood

- chain logs/state for exact pool/token;
- route/recovery and L2 provider health;
- official asset-registry changes;
- chain-specific venue/account decoders.

Do not claim Solana exact-account subscription semantics on EVM. Each event decoder/source has its own gap/finality version.

## 11. Failure taxonomy additions

- `CHAIN_ID_MISMATCH`;
- `RPC_STALE_BLOCK`;
- `ALLOWANCE_REQUIRED`;
- `ALLOWANCE_TARGET_INVALID`;
- `BALANCE_INSUFFICIENT`;
- `BUY_TAX_OR_TRANSFER_REVERT`;
- `SELL_TAX_OR_TRANSFER_REVERT`;
- `BLACKLIST_OR_RESTRICTION_SUSPECTED`;
- `SIMULATION_INCOMPLETE`;
- `L1_FEE_UNKNOWN`;
- `RWA_REGISTRY_STALE/UNAVAILABLE`;
- `RWA_EXCLUDED`;
- `ROUTE_NO_LIQUIDITY`;
- future `NONCE_CONFLICT`, `REPLACEMENT_UNDERPRICED`, `DROPPED_TRANSACTION`, `REORGED`, `RECEIPT_BALANCE_MISMATCH`.

Unknown errors remain explicit and versioned; do not map everything to no-route.

## 12. Future Live nonce/send/reconcile

Not implemented now. Required later:

- isolated per-chain signer and RPC/network allowlist;
- nonce manager with pending/replacement reconciliation;
- attempt before send;
- decode/validate transaction target/value/calldata/allowance locally;
- current simulation;
- send and receipt confirmation;
- log/balance reconciliation including taxes/fees;
- ambiguous/dropped/reorg state handling;
- physical portfolio limits and emergency exit policy.

Never blind-resend an unknown nonce transaction.

## 13. Promotion sequence

### BSC

1. discovery/asset correctness;
2. 0x firm amount-specific BUY/SELL observer;
3. realistic taker + allowance/build/simulation;
4. cost/tax/failure completeness;
5. forward research outcomes;
6. separate BSC Paper registration;
7. strategy sample maturity;
8. future Live review.

### Robinhood

1. official exact RWA/Stock Token exclusion;
2. firm route/build/simulation observer;
3. L2/L1/ETH cost completeness;
4. Meme-like cohort/sellability outcomes;
5. separate Robinhood Paper registration;
6. future Live review.

No historical token/winner backfill at any stage.

## 14. Tests

- wrong chain/address/decimals rejected;
- indicative price cannot create Paper fill;
- attempt row precedes provider call;
- BUY minimum acquired amount feeds SELL preflight;
- tax/transfer simulation failure blocks executable Paper;
- allowance target/version validated;
- gas/L1/approval costs not double-counted;
- Robinhood exact RWA address excluded, same ticker different address not automatically excluded;
- registry late update cannot rewrite old decision;
- no-route/error/late remain separate;
- BSC/Robinhood outcomes and costs never share one registration;
- no API key/taker private key/calldata exposed publicly;
- Live remains locked.

## 15. Current decision

Do not resume EVM coding before v5 shared Paper kernel is operational on Solana. Preserve existing BSC/Base/Robinhood research rows. When Gate L begins, BSC is first because its Meme/DEX universe provides the nearest economic test; Robinhood follows after the exact RWA exclusion and L2 fee path are current and validated.
