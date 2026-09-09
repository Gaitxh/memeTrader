# OpenFour P0-B feasibility audit 74

**Scope and cutoff.** Read-only source and chain audit, completed at 2026-09-09T05:41:04Z.  No runtime, strategy, database, request cadence, account, or execution change was made.  The raw public-RPC result is [chain_probe_20260909T054104Z.json](../../data/research/four74/chain_probe_20260909T054104Z.json); its reproducer is `data/research/four74/probe_openfour.mjs`.

## Authority and identity boundary

The requested GitHub URL `openfour-docs/blob/main/integration-guide.md` now returns 404 because the maintained file moved to `docs/integration-guide.md`.  The official repository was cloned at commit `0527d529d59c6a3fbc9927ce391ecc97c66e1b01` (2026-09-09T00:26:09+08:00; SHA-256 of the guide: `3C74EF4C42E9F8138FF16488F22B68EE3E019576ABEAC996E5011A4928CABE15`).  The authoritative current guide is [OpenFour Integration Guide](https://github.com/four-meme-community/openfour-docs/blob/main/docs/integration-guide.md), not the removed path.

It defines OpenFour as a modular launch engine with a Registry -> current Core/Tools discovery path.  An OpenFour token is identified first by `core.tokens(token).exists`; token and module descriptors refine the type.  The guide says internal quotes come from current Tools estimates and internal trading is phase-dependent, while a migrated token must move to an external DEX route.  It does not make a Four.meme listing row, a symbol, or an ordinary Four.meme TokenManager event proof that a token belongs to OpenFour.

This is distinct from the repository's current **Classic Four.meme** integration:

| Identity | Present local binding | What it proves | What it does not prove |
| --- | --- | --- | --- |
| Classic Four.meme | `TOKEN_MANAGER2 = 0x5c952063c7fc8610ffdb798152d69f0b9550762b`; only `TokenCreate` and `LiquidityAdded` decoded in `src/memetrader/four_meme_observer.py`; the REST observer uses `/public/token/search` | Narrow Classic create/listing evidence | OpenFour membership, curve trade flow, an external pool, or USD price |
| OpenFour | Registry `0x912CEf0C3aE9Ab6eB3Ec87cab69371cFb317Ab94`; current Core and Tools must be read from it | Registry-bound OpenFour protocol identity; per-token membership only when `core.tokens(token).exists` is true | Membership for any Classic token without that positive call; an always-current Core address |

## Current chain evidence

The calls below used BSC public RPC `https://bsc-rpc.publicnode.com` and `eth_call` only.

| Read | Result |
| --- | --- |
| `eth_chainId` / Registry code | `0x38` (BSC) / 209 bytes |
| `Registry.openFourCore()` | `0xebe7b6c1089d9f72ad07f34e36d898e44e5e27f3` (209-byte proxy code) |
| `Registry.openFourTool()` | `0x97da82f56fef1a0b974587a48135fa9da2a4e905` (209-byte proxy code) |
| `Core.wrappedNative()` | WBNB `0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c` |
| `Core.tokens(address(0))` | 704-byte ABI response; `exists=false`, `paused=false` |

The zero-address call is a negative ABI/path control only.  It does **not** establish that a real OpenFour token exists or is tradable.  Core and Tools are Registry-resolved proxy addresses, so a future observer must refresh the Registry rather than hardcode either address.

## Current prospective Four identities

To classify actual current Four.meme REST identities rather than infer from the empty OpenFour event window, the existing official `POST /meme-api/v1/public/token/search` source was read once at `2026-09-09T05:50:32.9711193Z`.  The first 10 unique valid BSC addresses (7 `PUBLISH`, 3 `INIT`) were each queried against the Registry-resolved Core at the **same** BSC block `0x733a591`.  The source rows and read results are preserved in [four_rest_current_identity_sample_20260909T055032Z.json](../../data/research/four74/four_rest_current_identity_sample_20260909T055032Z.json).

| Classification at block `0x733a591` | Count |
| --- | ---: |
| `core.tokens(token).exists == true` (OpenFour) | 0 |
| `core.tokens(token).exists == false` (not managed by the current OpenFour Core) | 10 |
| RPC/decode errors | 0 |

The present sample is therefore **10/10 current Four REST identities that are not OpenFour under the current Registry Core**.  It does not prove that every one is a Classic `TOKEN_MANAGER2` event identity, because this bounded check deliberately did not add a Classic-log source.  The correct labels are: `Four REST candidate / OpenFour=no / Classic-chain-event=unverified`; never infer OpenFour from the shared Four.meme brand, token name, symbol, or API row.

No OpenFour-positive row existed, so there is no OpenFour `quoteAsset` to report.  The REST field `symbol` in these rows (`NVDAB`, `QQQB`, `BNB`, `USD1`, `GMEB`, `SPCXB`) is provider metadata, not an ERC-20 quote-asset address and not a USD conversion.  The provider's price/cap fields remain non-USD raw data under the existing observer contract.

## Bounded coverage and USD availability

The event topic was derived from the official `TokenCreated` ABI.  PublicNode returned **0** matching `TokenCreated` logs in the immediately preceding **8,192** blocks, from `0x73380a2` through `0x733a0a2`, at the capture time.  Thus:

| Measure | Result | Interpretation |
| --- | ---: | --- |
| Positive OpenFour token sample | 0 / 10 current REST candidates | All ten have `tokens.exists=false` at the same block; no token could be checked with `exists=true`, Vault phase, quote asset, or Tools quote. |
| Bounded current event coverage | 8,192 blocks, 0 events | A short current-window result only; it is not historical coverage or evidence that the protocol has no tokens. |
| Causal OpenFour USD conversions | 0 / 0 token samples | No per-token quote asset and no same-receipt USD conversion pair were observed. WBNB is the Core's wrapped native asset, not proof that every token uses WBNB or that a USD conversion was available at a token's decision time. |
| Existing Classic Four listing evidence | Not used as this audit's denominator | Current 10-address REST/Core sample above is the identity evidence; historical native-launch53 counts are deliberately not reused. |

The configured Classic REST observer intentionally does not emit `price_usd`; it records provider raw values as non-USD.  Therefore neither its rows nor the OpenFour Tools raw quote units can enter Paper valuation without a local, timestamped quote-asset-to-USD observation available no later than the decision.  A current WBNB price fetched after the fact would be future data for an earlier token decision.

`https://bsc-dataseed.bnbchain.org`, the project’s existing BSC observer endpoint, rejected `eth_getLogs` even for a one-block topic-filtered request with `-32005 limit exceeded`.  PublicNode accepted the bounded query but its free endpoint rejected 50,000-block historical queries as archive-only.  These are concrete coverage limits, not evidence about token activity.

## Disposition

**P0-B OpenFour is not ready for an execution or strategy integration.** Registry/Core discovery and the negative `tokens` control are verified, but the required positive identity sample, phase/quote data, and causal USD conversion coverage are all absent.  No Classic-to-OpenFour alias may be inferred.

The smallest safe next step, if separately approved, is a **shadow-only** observer: refresh Registry -> Core/Tools, keep a bounded overlapping `TokenCreated` cursor on an endpoint that actually supports logs, require `tokens.exists=true` before recording an OpenFour identity, then record raw quote asset, phase, and Tools estimates with receipt timestamps.  It must leave `USD_UNKNOWN` and make no Paper/BUY decision unless the same as-of record contains an independently captured quote-asset USD conversion and the appropriate current internal/external route.  Before implementation, demonstrate at least one positive `exists=true` sample and one complete as-of USD conversion through the selected public source.
