# V5 Reverse Sellability Probe versus Sequential Execution Truth

Date: 2026-09-04
Status: `P0 ECONOMIC CORRECTION / FOLD INTO GATES A-C`

## 1. Problem

The current research/Paper pattern requests:

1. an amount-specific USDC→Token BUY quote;
2. a Token→USDC SELL quote using the BUY minimum token output.

Both requests normally observe the **same pre-BUY chain state** because no transaction was executed between them. This is valuable sellability/capacity evidence, but it is not a simulation of the sequential path `BUY changes state -> acquired balance -> SELL from the changed state`.

Calling the ratio an exact immediate round-trip recovery can overstate its truth. The direction of bias is not universally guaranteed across direct pools, multi-hop routes, alternative venues, transfer behavior and concurrent state changes.

## 2. Required terminology and evidence classes

### `ENTRY_BUY_QUOTE`

Current amount-specific BUY plan/quote:

- exact input amount;
- central/minimum token output;
- route/state/context/time;
- no fill guarantee.

### `SAME_STATE_REVERSE_SELLABILITY_PROBE`

A current SELL quote for the conservative BUY minimum token amount, requested before the BUY executes and therefore based on an independently observed current state.

It demonstrates:

- a reverse route can currently be found for that token amount;
- current route capacity/price impact/minimum output under the probe state;
- deterministic API/token/address/amount compatibility;
- a useful liquidity/cost-risk proxy.

It does **not** demonstrate:

- the route after the BUY has changed pool balances;
- actual acquired balance after transfer/tax;
- guaranteed future sellability;
- sequential round-trip fill/recovery;
- future landing/MEV/state competition.

### `STATE_ADJUSTED_SEQUENTIAL_ESTIMATE`

Available only when all relevant route legs/state/fee/transfer semantics can be modeled in order. Examples:

- exact supported direct AMM pool formula with current reserves and versioned fees;
- a maintained local/fork/state-override simulation that applies the BUY state before simulating SELL;
- another validated sequential method.

Store model/source/version and limitations. Do not claim exact for opaque/multi-hop routes whose state transition is incomplete.

### `POST_BUY_CURRENT_SELL_QUOTE`

A fresh amount-specific SELL quote obtained after a real BUY confirmation/balance acquisition. For Paper, this is a later real-market observation after the virtual entry time; it still cannot include the nonexistent Paper trade’s physical market impact.

It is the operational sellability truth for a future Live position and the current economic valuation/exit input after entry.

### `LIVE_RECONCILED_ROUND_TRIP`

Future actual confirmed BUY/SELL balance and fee deltas. Unavailable while Live is locked.

## 3. V5 field corrections

Replace ambiguous fields such as:

- `quoted_net_recovery_ratio`;
- `immediate_round_trip_recovery`;

with explicit names or evidence-class metadata:

- `reverse_probe_central_recovery_ratio`;
- `reverse_probe_min_recovery_ratio`;
- `reverse_probe_state_relation = same_pre_buy_state`;
- optional `sequential_estimate_*`;
- `post_buy_sell_*`;
- `evidence_class`;
- `execution_truth_level`.

Historical v4 fields/rows remain unchanged. V5 adapters translate them only as historical/source evidence and never silently upgrade them.

## 4. Entry policy use

The reverse probe remains a common executable-Paper prerequisite when it proves a current route for the conservative acquired amount. It is not a guarantee.

Policy/risk buckets use `reverse_probe_min_recovery_ratio`, explicitly labeled. For example, prior R0/R1/R2 bands remain design priors only after renaming from “round-trip recovery” to “same-state reverse-probe recovery”.

A positive probe does not eliminate rug/transfer/route-state risk. A missing probe means no current executable sellability evidence and therefore research-only/no Paper fill under the first v5 version.

## 5. Paper fill and PNL

### Entry

- virtual Paper BUY acquired amount is the registered conservative BUY minimum output;
- one shared observation may support exact-identical virtual allocations;
- no chain state is changed by the Paper fill.

### After entry

- actual policy valuation/exit uses later current amount-specific SELL quotes for the remaining virtual amount;
- a DEX mark or the original reverse probe is not carried forward as current value;
- no route remains a categorical state;
- terminal writeoff follows the registered exact predicate.

The original reverse probe is an entry risk feature, not an exit fill or realized PNL.

## 6. Self-impact and virtual accounts

A 20 USDC reverse probe describes the market for one 20 USDC BUY-minimum token quantity on the current state. Four virtual strategy allocations may reference the same observation because they are counterfactual paired accounts.

Do not infer:

- an 80 USDC aggregate physical route/recovery;
- four physical trades with zero mutual impact;
- that a future Live aggregate can reuse the observation.

Future physical aggregation requires an exact aggregate BUY plan and its own sequential/self-impact evidence.

## 7. Direct canonical PumpSwap research

For exact supported direct PumpSwap routes, a research layer may calculate a state-adjusted sequential estimate:

1. decode current reserves/config/fees;
2. apply exact BUY input and conservative transfer/fee rules;
3. update reserves/state;
4. apply SELL of the acquired amount;
5. calculate quote return and explicit costs;
6. compare with the two independent Jupiter quotes;
7. store divergence/model version.

This can improve entry economics and identify route-probe bias. It remains an estimate until real execution is reconciled. Multi-hop/opaque routes stay reverse-probe-only unless every state transition is modeled.

## 8. Concurrent market movement

Between BUY quote, reverse probe, future BUY send and SELL:

- slots and pool states change;
- routes/venues can change;
- competing trades alter reserves;
- blockhash/quote expires;
- token rules/admin state may change.

Persist request/context/completion slot/time for each leg. Do not call asynchronous quotes simultaneous/atomic. Freshness/latency becomes a risk feature and Live release gate.

## 9. Cost implications

The simplified `0.96 × 0.96` example is a conservative arithmetic illustration, not a state-adjusted AMM round trip. V5 reports:

- BUY minimum output;
- same-state reverse minimum output;
- optional sequential estimate;
- later post-entry current sell output;
- actual Live reconciled outcome when available.

Never subtract route fee/slippage twice.

## 10. Web labels

Use:

- `BUY QUOTE — CURRENT STATE`;
- `REVERSE SELLABILITY PROBE — SAME PRE-BUY STATE`;
- `SEQUENTIAL ESTIMATE — MODELLED`;
- `POST-BUY CURRENT SELL QUOTE`;
- `LIVE RECONCILED`.

Do not display “immediate guaranteed recovery”. Tooltip explains that the reverse probe proves current route/addressability for the amount, not the post-BUY state.

## 11. Learning and labels

Study reverse-probe predictive value against:

- first post-entry current quote;
- 15/60/240m amount-specific sellability;
- terminal strategy PNL;
- no-route/dead/writeoff;
- future Live realized recovery if ever available.

This determines whether R0/R1/R2 bands are useful without treating the probe as ground truth.

## 12. Tests

- BUY and reverse probe store distinct request/context/response clocks;
- reverse probe is tagged `same_pre_buy_state`;
- reverse probe cannot create a SELL fill or current position value;
- later exit requires a new current quote;
- v5 fields/UI do not call it exact sequential round trip;
- direct sequential model is used only for supported exact routes and versioned;
- opaque/multi-hop route cannot be silently state-adjusted;
- four virtual allocations can share one observation but not create an aggregate physical claim;
- historical v4 rows are not mutated/reinterpreted as stronger evidence;
- Live remains locked.

## 13. Immediate Codex impact

Gates A-C schema/API must reserve the evidence-class/state-relation distinction. The first v5 lifecycle may persist only BUY quote + same-state reverse sellability probe; it must not name or report the latter as a true sequential round-trip fill. Gate D risk buckets use the renamed reverse-probe ratios. A later direct-PumpSwap sequential estimator belongs after MarketFrame/decoder validation.
