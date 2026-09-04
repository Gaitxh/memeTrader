# V5 Execution Cost Truth Specification

Date: 2026-09-04
Status: `P0/P1 ECONOMIC CONTRACT / CURRENT PROTOCOL FIELDS OVER LEGACY CONSTANTS`

## 1. Problem

Meme strategy profitability is highly sensitive to round-trip costs. The current project has used several different comparison contracts over time, including configured adverse slippage, fixed network-fee approximations and a PumpSwap fee assumption. These are useful versioned Paper contracts, but they must not be described as universally current protocol/live cost.

V5 separates route output, execution uncertainty and explicit costs so no fee is omitted or deducted twice.

## 2. Cost layers

### Layer A — route/output economics

For each amount-specific quote/plan store:

- exact input amount;
- central output (`outAmount` or adapter equivalent);
- minimum/threshold output (`otherAmountThreshold` or equivalent);
- slippage mode/bps used to construct the threshold;
- price impact;
- normalized route legs;
- per-leg fee amount/mint/label fields exposed by the router;
- platform/referral fee fields;
- request/context/response clocks.

AMM/router fees and price impact that are already embodied in the quoted output are not subtracted again from account cash.

### Layer B — conservative execution bound

The first v5 conservative Paper account uses the valid minimum output for the exact input. This captures the registered adverse-slippage bound supplied by the router response. It is a conservative quote bound, not a guaranteed fill or a second explicit fee.

Do not apply another 4% haircut after booking the 400-bps threshold unless a separately registered fill model explicitly defines an additional effect and proves it is not double counting.

### Layer C — explicit transaction/network costs

Separate fields:

- Solana base transaction fee;
- priority/compute-unit fee;
- token account creation/rent where applicable;
- router/platform fee not already embodied in output;
- future Jito tip/bundle fee;
- EVM gas and approval transaction cost;
- EVM L1 data fee;
- token transfer/tax amount;
- failed transaction/simulation/send cost;
- same-time native-token/USD conversion source/time.

A missing field is `unknown`, not zero.

### Layer D — landing/MEV/fill uncertainty

Examples:

- quote-to-send state change;
- transaction not landing;
- partial/changed route;
- sandwich/frontrun loss;
- blockhash/nonce expiry;
- priority fee inadequacy;
- unmodeled token behavior.

Quote-only Paper labels this uncertainty; it does not silently convert it into an arbitrary fee. A future fill model needs independent reconciled execution data and a new version.

## 3. PumpSwap/protocol fee handling

Do not hard-code a historical `125 bps` as current truth for every PumpSwap route/time.

Use, in priority order:

1. actual amount-specific router output and route-plan fee fields at the request time;
2. current on-chain/program configuration/account facts decoded under a versioned official interface, for explanation/cross-check;
3. a configured comparison assumption only when the first two are unavailable, labeled `modeled_legacy_assumption` and never added on top of an output that already embodies the fee.

Protocol/creator/LP fee schedules/configuration can change. Persist the source account/config/interface version and availability time when used. A later current config cannot be backfilled into an earlier trade.

## 4. Paper economic views

### `CONSERVATIVE_QUOTE_BOUND`

- central input cash spent;
- minimum acquired/proceeds output;
- explicit known non-duplicated costs;
- unknown cost fields remain incomplete.

This is the account-authoritative v5 Paper view initially.

### `CENTRAL_QUOTE_ESTIMATE`

- central output;
- explicit known non-duplicated costs;
- non-guaranteed estimate.

Never mix its cash/PnL with the conservative account.

### `SIMULATION_COMPLETE_ESTIMATE`

Available later when a full transaction is built/simulated and all relevant chain fees/taxes are estimated. Still not a fill.

### `LIVE_RECONCILED`

Future actual confirmed balance/fee deltas. Unavailable while Live is locked.

## 5. Cost-completeness states

Suggested ordered states:

- `route_output_only`;
- `route_plus_partial_network_estimate`;
- `simulation_complete_estimate`;
- future `live_reconciled`;
- `unknown_or_invalid`.

A strategy can collect Paper evidence with incomplete cost, but cannot be described as Live-economics complete. Cross-policy/chain ranking must either use the same cost layer or disclose the mismatch.

## 6. Entry preflight economics

For 20 USDC:

1. obtain amount-specific BUY central/minimum output;
2. use the conservative acquired raw amount as immediate SELL input;
3. obtain amount-specific SELL central/minimum output;
4. compute immediate recovery from the SELL output;
5. subtract only explicit known costs not already in route outputs;
6. store central/minimum recovery and completeness separately.

`positive output` proves only that some route exists. It does not prove acceptable economics. Recovery bands are policy/risk features; no-route/impossible transfer is no executable Paper fill.

## 7. Partial exits

Every tranche gets its own exact plan:

- desired raw token amount;
- central/minimum USDC output;
- route/fee/price-impact fields;
- explicit transaction costs;
- resulting remaining amount/cost.

Do not scale a full-position quote linearly or allocate one transaction fee across hypothetical fills without a registered rule.

When several virtual strategies reference one exact-identical quote observation, each independent virtual account applies the same cost semantics. This does not create one physical transaction or share one future network fee across four physical orders.

## 8. Failed attempts

Quote/provider failures typically do not create an on-chain network cost. Future built/sent transaction failures may.

Store separately:

- quote attempt no-route/error/late: no fill, no chain fee;
- simulation failure before send: no fill; API/compute cost outside trading PNL unless explicitly modeled;
- future submitted transaction failure: actual chain fee/tip from receipt/reconciliation;
- ambiguous send: no duplicate fill/retry until reconciled.

Do not assign the current fixed 0.40 USDC to every failed quote merely because it was an operational attempt.

## 9. Native-token conversion

Network fees in SOL/BNB/ETH need a conversion observed/available at the transaction/plan time:

- source and pair;
- observed/received/recorded time;
- conversion price;
- missing/stale status.

A later daily price cannot be used as the earlier decision cost without explicit outcome-only labeling.

For Paper, cost can remain native plus USD unknown until a valid conversion exists; do not silently use zero.

## 10. 4% comparison contract

The current 400-bps threshold remains useful because it creates a conservative and comparable minimum-output bound. It should be described as:

- router slippage/minimum-output policy;
- not automatically the realized slippage;
- not an additional 4% debit after the threshold;
- not necessarily optimal for future Live;
- versioned by strategy/chain/urgency.

A future emergency exit may use wider tolerance; that is a new explicit policy version and does not rewrite Paper history.

## 11. Strategy economics

Report for every strategy:

- conservative route-bound PNL;
- central quote estimate;
- known explicit network/tax cost;
- unknown/incomplete cost exposure;
- no-route/writeoff;
- capital time;
- provider/quote count and latency;
- future actual reconciled PNL only when available.

Do not improve PNL by switching cost layer mid-series.

## 12. Multi-chain implications

### Solana

- Jupiter route output/threshold and fee fields;
- base/priority/account-creation fee via transaction simulation/build when available;
- future tip/landing/reconciliation separately.

### BSC

- route output, token taxes, approval/BUY/SELL gas;
- failed transaction costs and MEV uncertainty;
- BNB/USD time-valid conversion.

### Robinhood Chain

- route output/taxes;
- ETH L2 gas + L1 data fee;
- approval/failure cost;
- time-valid ETH/USD conversion.

No chain inherits another chain’s flat-cost profile.

## 13. Validation and reconciliation

Required checks:

- central output >= minimum output when semantics require;
- input/output decimals and mint direction correct;
- route fee fields preserved and not double-subtracted;
- cost fields have sources/times/completeness;
- account cash changes exactly equal immutable virtual fills under the selected view;
- position events allocate entry cost/partial proceeds consistently;
- current projection rebuilds from fills/events;
- old cost versions remain immutable.

## 14. Tests

- 400-bps threshold is not followed by a second 4% debit;
- route fee already in output is not separately deducted;
- missing priority/native conversion stays unknown;
- failed quote creates no fill/network fee;
- future failed sent transaction can carry reconciled chain fee;
- conservative and central accounts/views cannot mix;
- partial exact-size costs update remaining cost correctly;
- current protocol/config observed later cannot backfill earlier trade;
- BSC/Robinhood cost fields remain separate;
- Live remains locked.

## 15. Current decision

V5 does not wait for perfectly complete Live costs before Paper learning. It uses the conservative current amount-specific route bound and labels cost incompleteness honestly. Capital promotion and cross-chain comparison require progressively better simulation/reconciliation, not an invented universal fixed fee.
