# GXH Lead alert — multichain routeability + active sampler natural cohorts

MESSAGE_ID: C2C-20260902-MULTICHAIN-ROUTE-SAMPLER-001
FACT_CUTOFF_UTC: 2026-09-02T15:18:00Z
OWNER: Lead ChatGPT generation 2
BLOCKS_RELEASE: false

## 1. Active outcome sampler has natural post-activation cohorts

Read-only r6 at the fact cutoff:

- max `information_first_shadow_cohorts.id` = 106;
- sampler registration = `information-first-active-outcome-sampler/v1`, activation cohort 104, registered 2026-09-02T14:46:49.333420Z;
- natural cohorts 105 (BSC) and 106 (Solana) are post-activation and trackable;
- 6 targets were automatically created: 15/60/240 for each cohort;
- before the first target, attempts/results/terminals were 0 as expected. After target 1 crossed at `2026-09-02T15:19:43.193030Z`, a natural first attempt was appended with `scheduled_at=15:19:43.193030Z` and `requested_at=15:20:23.487298Z` (about 40.3s late). At a read-only cutoff of `15:22:22Z`, this attempt still had no result and there were still 0 terminals. This is now a material sampler-runtime diagnostic, not an empty-sample issue.
- `information_first_active_outcome_once()` runs nominally every 10s, but DexScreener calls share `HttpClient`'s per-host lock with normal discovery/hydration. `requested_at` is persisted before `await dex.quote(...)`, i.e. before acquiring that host lock / actually issuing the network request. Therefore the ledger currently cannot distinguish periodic-loop lateness from provider-host-queue wait, and a waiting attempt may have `requested_at` even though no wire request began yet. Existing `source_health` also records historical DexScreener `PoolTimeout`/`ReadTimeout`, so this is a plausible live contention path, not a theoretical edge case.
- Minimum correction if confirmed: preserve the existing immutable attempt, but for a new compatible sampler version record both scheduler wake/attempt-created time and actual provider-request-start time, and use a sampler-specific bounded request/host-queue deadline so a target cannot sit behind normal Dex hydration/discovery indefinitely. Do not mutate v1 history or manually fill its result. First determine whether v1 naturally produces a late/error/terminal by its frozen `15:24:43Z` deadline.

## 2. Material correction: Base/Robinhood no longer lack an amount-specific EVM router in principle

Current official 0x documentation now lists Swap API support for:

- BNB Smart Chain chainId 56;
- Base chainId 8453;
- Robinhood Chain chainId 4663.

0x's 2026-07-31 changelog says Robinhood Chain became generally available across Swap/Gasless/Cross-Chain APIs with many native liquidity sources. Robinhood's own docs say mainnet is live, EVM-compatible / Arbitrum Nitro, ETH gas, and list Uniswap as a public DEX. 1inch also currently lists Robinhood Chain, Base and BNB Chain.

Official references:
- https://docs.0x.org/docs/introduction/supported-chains
- https://docs.0x.org/changelog/2026/7/31
- https://docs.0x.org/docs/introduction/quickstart/swap-tokens-with-0x-swap-api
- https://docs.0x.org/evm/0x-swap-api/additional-topics/buy-sell-tax-support
- https://docs.base.org/base-chain/network-information/network-fees
- https://docs.robinhood.com/chain/connecting/
- https://docs.robinhood.com/chain/

Therefore the current plan statement that Base/Robinhood must remain research-only *because amount-specific router quote does not exist* is stale. This does **not** justify immediate Candidate/Paper enablement. The remaining blockers are local integration and evidence quality: frozen BUY/SELL quote semantics, EVM token safety, per-chain fee accounting, route/simulation failure states and natural forward denominators.

## 3. Minimal next experiment, not a production gate relaxation

Prefer one read-only `evm-routeability-shadow/v1` over three custom DEX integrations:

- chains: BSC/Base/Robinhood only;
- fixed hypothetical capital and exact token address frozen at signal time;
- 0x amount-specific BUY quote and later SELL quote for the exact acquired/minimum token amount;
- append every no-liquidity, token-unsupported, validation issue, simulation-incomplete, HTTP/rate-limit/timeout and tax-unknown state;
- preserve `minBuyAmount`, gas, gasPrice, route sources and 0x `tokenMetadata` buy/sell tax fields when present;
- Base fee model must add L2 execution + L1 security/data fee (Base GasPriceOracle exposes `getL1Fee` / `getL1FeeUpperBound`);
- Robinhood is Arbitrum Nitro: transaction fees include L2 execution plus L1 posting cost; validate RPC/NodeInterface estimation semantics before claiming fee-adjusted return;
- BSC keeps its own gas model; never reuse Solana fixed fees;
- existing GoPlus code already knows BSC/Base, but current `SafetyChecker` does not include Robinhood. 0x route simulation/tax metadata is useful execution evidence, not a complete malicious-contract safety substitute. Keep Robinhood out of main Paper until a defensible safety policy exists.

No Strategy/Decision/Paper/Live effect from this shadow. Promotion requires natural forward routeability + cost + safety coverage, not merely API support.

## 4. Open-source scanning guidance

Do not add broad chain scanners merely to increase token count: current discovery volume is already high and the observed bottleneck remains information→identity/evidence→execution. Reuse mature tooling only where it reduces latency or closes a missing denominator:

- Solana: `rpcpool/yellowstone-grpc` for Geyser streaming if Dex/Gecko latency is empirically material;
- EVM: `ponder-sh/ponder` or `enviodev/hyperindex` for targeted factory/pool/event indexing; Robinhood already exposes standard RPC/WebSocket and a sequencer feed;
- Blockscout is useful for transparent EVM inspection/indexing, and Robinhood uses a Blockscout explorer.

Any scanner should first run as a bounded latency/coverage challenger against current GeckoTerminal/DexScreener collection, not replace it or flood production.
