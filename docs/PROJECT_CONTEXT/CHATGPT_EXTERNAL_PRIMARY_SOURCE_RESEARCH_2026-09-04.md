# External Primary-Source Research for the Profit-First Meme Trading System

Date: 2026-09-04
Status: `RESEARCH INPUT / NOT A TRADING SIGNAL / VERIFY AGAINST CURRENT LOCAL FORWARD DATA`

## 1. Research standard

External sources are used for four purposes only:

1. establish protocol/interface semantics;
2. identify maintained implementation paths before custom engineering;
3. generate falsifiable market hypotheses;
4. define failure modes the local system must record.

No external document proves the current strategy profitable, selects a production threshold, authorizes a Live release, or replaces current r6/code evidence.

## 2. Solana realtime observations

### Official `accountSubscribe`

Source: `https://solana.com/docs/rpc/websocket/accountsubscribe`

What it establishes:

- a client can subscribe to changes for a specific public key;
- notifications carry slot context and an account value;
- commitment and account-data encoding are explicit request choices.

What it does not establish:

- the semantic meaning of a PumpSwap pool/vault/mint change;
- guaranteed delivery without reconnect/gap handling;
- transaction ordering across several independent subscriptions;
- sellability or economic recovery.

Project implication:

- keep the existing exact pool/base-vault/quote-vault/mint/LP-mint subscription design;
- save slot, receive time, local availability time and reconnect/gap state;
- use subscription changes as fast risk facts, then map them through exact account decoders and a fresh full-position quote;
- never infer a rug from the mere absence of notifications.

### Official `logsSubscribe`

Source: `https://solana.com/docs/rpc/websocket/logssubscribe`

What it establishes:

- transaction log notifications can be streamed with slot/signature/error/log records;
- filtering is available, but the exact filter semantics and limits must be respected.

What it does not establish:

- decoded PumpSwap trade amounts/direction;
- complete account-state deltas;
- absence of gaps or provider-specific loss;
- global low-latency ordering by itself.

Project implication:

- use a Pump program/PumpSwap log stream as a candidate transaction clock, then fetch/decode only relevant transactions/pools;
- combine it with exact account changes rather than choosing one source as universal truth;
- record stream gaps and decode failures in the market-frame denominator.

## 3. Pump public IDLs and interfaces

Source: `https://github.com/pump-fun/pump-public-docs`

What it establishes:

- official/public interface definitions exist for Pump and PumpSwap;
- account, instruction and event layouts can be versioned and decoded deterministically;
- canonical PDA/account relationships can be validated against the published program interface.

What it does not establish:

- that every pool labeled “PumpSwap” by an aggregator is a canonical Pump migration pool;
- that all liquidity is economically reachable through the actual Jupiter route;
- that a decoded trade came from an independent buyer rather than coordinated wallets;
- that a token is safe or profitable.

Project implication:

- build decoder fixtures directly from the current public IDL and known transactions;
- store decoder/IDL version with every raw event and MarketFrame;
- fail closed for unknown account/event layout, while preserving the raw signature/slot reference;
- continue separating Holding Surface Safety from actual Execution Route Truth.

## 4. SPL Token / Token-2022 capabilities

Source: official Solana token-extension documentation, including `https://solana.com/docs/tokens/extensions`

What it establishes:

- Token-2022 can attach protocol-level extensions such as transfer fees, transfer hooks, permanent delegation, non-transferability and other controls;
- mint/account program owner and extension data can be decoded directly rather than inferred from a third-party risk score.

What it does not establish:

- whether a hook/delegate is malicious;
- that a legacy SPL mint is risk-free;
- actual router compatibility or economic sellability.

Project implication:

- retain direct mint/program/extension decoding as execution truth;
- distinguish deterministic transfer impossibility from uncertain risk;
- preserve GoPlus/Rugcheck-like services only as cross-check evidence, not the sole source of mint-control truth.

## 5. Jupiter amount-specific quote semantics

Sources:

- `https://dev.jup.ag/docs/swap-api/get-quote`
- Jupiter Swap quote API reference
- Jupiter Ultra `/order` documentation

What they establish:

- quote requests are amount-specific and direction-specific;
- a response exposes central output, minimum/threshold output, slippage settings, price impact and route plan/context timing fields;
- route plans can contain multiple legs and venues;
- order/build APIs can return a transaction plan when required execution fields are supplied.

What they do not establish:

- guaranteed on-chain fill at the quoted amount;
- that a route remains available after response;
- that the selected DexScreener pair is the executed holding/route surface;
- full priority-fee, landing probability, MEV and state-change cost without execution/reconciliation;
- that a quote-only path is Live-ready.

Project implication:

- keep `outAmount`/central estimate separate from `otherAmountThreshold`/conservative bound;
- store request, context slot, response and local availability clocks;
- persist every route leg and its relation to the selected holding surface;
- a Paper fill must reference the exact plan/attempt and clearly label cost completeness;
- the future Live adapter requires build/simulation/send/confirmation/balance reconciliation rather than simply replacing “Paper” with “Live”.

## 6. Yellowstone/Geyser as an escalation path

Source: maintained `rpcpool/yellowstone-grpc` project and Solana Geyser ecosystem documentation.

What it establishes:

- Geyser-based gRPC streams can deliver filtered accounts, transactions, slots and blocks at higher throughput/lower overhead than repeated polling;
- filter/resume/keepalive behavior is an established implementation path rather than a project-specific invention.

What it does not establish:

- that the current native WebSocket path is inadequate;
- a free/public provider SLA;
- decoded PumpSwap semantics or strategy edge;
- immunity from gaps/reorg/endpoint failure.

Project implication:

- first measure native WebSocket receive-to-frame p50/p95, gap rate and CPU/network load on exact held/candidate pools;
- promote Yellowstone only when measured latency/reliability blocks the exit SLO;
- preserve the same event/frame schema so the transport can change without changing strategy definitions.

## 7. Jito low-latency transaction path

Source: official Jito low-latency transaction-send documentation.

What it establishes:

- transactions/bundles can be submitted through a validator-connected low-latency path;
- tip, bundle and preflight semantics differ from standard RPC submission and must be explicit.

What it does not establish:

- guaranteed landing or profit;
- safety of skipping simulation;
- suitability for this project before a signer/reconciliation system exists;
- that Jito is needed for Paper research.

Project implication:

- keep it as a future Live execution-adapter candidate only;
- do not add it to the current P0 or let it weaken simulation, idempotency and balance reconciliation;
- compare landing/latency/cost only after a locked small-capital release protocol exists.

## 8. 0x and EVM chain support

Source: `https://docs.0x.org/docs/introduction/supported-chains` and official Swap API documentation.

What it establishes:

- 0x exposes amount-specific aggregation on supported EVM networks, including BNB Smart Chain and Robinhood Chain where listed by the current official documentation;
- price/quote responses can expose route, allowance, balance, gas/network fee, token tax and simulation-related fields depending on endpoint/version.

What it does not establish:

- that an indicative price is a firm executable fill;
- complete protection from fee-on-transfer, blacklist, honeypot or state change;
- that all returned assets are Meme tokens;
- profitability after gas/L1 data fee/MEV.

Project implication:

- use a firm quote/transaction simulation path, not pool-math or indicative-price-only, before EVM Paper promotion;
- write attempt-before-network, exact amount, block/context, tax/allowance/simulation/cost completeness and failure terminal;
- keep chain-specific adapters under the same generic OrderIntent/Plan/Attempt/Fill lifecycle.

## 9. Robinhood Chain official network facts

Sources: official Robinhood Chain connection/network documentation.

What they establish:

- Robinhood Chain is an EVM/Arbitrum-based network with its own chain ID/network endpoints and native fee semantics;
- the ecosystem intentionally includes tokenized real-world assets/stock-token products.

What they do not establish:

- that every new pool/token is a Meme opportunity;
- complete Meme/stock/RWA classification from symbol/name;
- router/safety/cost maturity.

Project implication:

- maintain an exact-address official stock/RWA exclusion registry with its own observation clock;
- never infer RWA status from ticker alone;
- only the remaining Meme-like cohort enters a chain-specific research/Paper funnel;
- Robinhood results never share BSC cost/safety assumptions merely because both are EVM.

## 10. Empirical research on Meme/rug behavior

### Early rug-pull detection on Pump.fun/Solana

Recent large-scale empirical work studies millions of tokens and reports that early transaction/liquidity/creator/holder behavior contains information about later rug-like outcomes, including very early windows.

What it contributes:

- supports collecting creator history, first minutes of trade flow, concentration, liquidity survival and sellability;
- motivates calibrated probability/hazard research rather than a single hand-written “rug score”.

What it does not contribute:

- a production threshold for this machine/provider/venue;
- guaranteed escape from atomic same-transaction liquidity removal;
- valid labels unless the paper’s rug definition matches this project’s exact-account/economic terminal.

Project implication:

- use the variables as challenger features;
- re-label outcomes under this project’s strict terminal definition;
- evaluate on future registered cohorts with all no-route/writeoff cases.

### Meme-token manipulation/wash-trading research

Recent cross-chain empirical work reports widespread manipulation/wash-like behavior among high-return Meme-token samples.

What it contributes:

- price/volume growth alone is not sufficient alpha evidence;
- wallet breadth, effective breadth, trade-size concentration, creator/cluster relationships and executable recovery deserve explicit measurement.

What it does not contribute:

- permission to identify each wallet as a unique human or malicious actor;
- a universal wash-trading classifier;
- evidence that every manipulated token is unprofitable for a fast strategy.

Project implication:

- compare raw wallet count with effective notional breadth and top-k concentration;
- treat manipulation risk as a strategy feature/risk bucket unless it creates deterministic transfer/execution impossibility;
- test whether Fast Escape monetizes some manipulated markets while preserving all terminal losses in ITT.

## 11. Source-to-implementation matrix

| Need | Preferred first source/path | Escalation | Not allowed as proof |
|---|---|---|---|
| Exact held-account risk | Solana `accountSubscribe` + direct decoder | Geyser/Yellowstone after measured need | Dex price stall alone |
| PumpSwap trade flow | Official logs/transactions + public IDL | filtered Geyser transaction stream | provider 5m summary alone |
| Solana execution | amount-specific Jupiter quote/plan | future build/simulation/send/reconcile | quote = guaranteed fill |
| Token controls | direct SPL/Token-2022 RPC decode | third-party cross-check | third-party “safe” score alone |
| BSC execution | 0x firm quote/simulation + chain RPC | alternate maintained router when measured | Quoter pool math = fill |
| Robinhood execution | exact RWA exclusion + 0x/chain adapter | alternative official router | symbol/name = Meme |
| Fast landing | normal simulated/reconciled path first | future Jito adapter | low latency = profitable |
| Rug/alpha hypothesis | local strict-forward labels/frames | calibrated model after sample maturity | paper threshold copied to production |

## 12. Research conclusion

The official ecosystem already provides the building blocks for a faster, more faithful system. The bottleneck is not a missing magic API. It is the project’s need to:

- preserve exact clocks and source gaps;
- decode the right pool/token facts;
- share observations across strategies;
- distinguish quote, simulation, fill and reconciliation;
- learn from every rejected, failed, no-route and dead case;
- keep broad Paper exploration separate from Live eligibility.

That is the basis for the v5 implementation order. No source above justifies bypassing the current Live lock or retroactively tuning v4.
