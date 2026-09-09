# Native curve feasibility 73

**Disposition: identity/state probe PASS; economic 5/20 USD round trips UNKNOWN; no runtime observer added.**

This is a bounded read-only study. It sent public HTTP/RPC `eth_call`s only: no key, signature, transaction, database evidence insertion, restart, or strategy action. Raw compact evidence is [`data/research/native73/probe.json`](../../data/research/native73/probe.json).

## Authority and present implementation

The existing native collectors are deliberately identity-only:

- [`four_meme_rest.py`](../../src/memetrader/four_meme_rest.py) labels provider amounts as non-USD and `buy_authority=False`.
- [`pons_observer.py`](../../src/memetrader/pons_observer.py) records the V2 curve and pair token from `TokenLaunched`, leaves the pool null, and calls its V2 evidence identity-only.
- [`launchlab_observer.py`](../../src/memetrader/launchlab_observer.py) preserves API listing identity and raw fields, explicitly without quote conversion or BUY authority.

This matches the earlier deployed evidence boundary in `NATIVE_LAUNCH_FOUNDATION_53.md` and `LAUNCHLAB_STONKFUN_FEASIBILITY_56.md`. No current code has the validated curve-state/asset-conversion semantics needed for a new economics observer.

## Four.meme Helper3

The official Four integration page links the `four-meme-community/fourmeme-docs` repository. Its [Helper3 ABI](https://raw.githubusercontent.com/four-meme-community/fourmeme-docs/main/abi/TokenManagerHelper3.lite.json) defines:

- `getTokenInfo(address)` → version, token manager, **quote asset**, state and fee fields;
- `tryBuy(address,uint256,uint256)` → estimate and required payment/approval fields; and
- `trySell(address,uint256)` → quote asset, funds and fee.

At fixed BSC block `0x733961d`, a current official-listing token `0x3e2f…ffff` returned Helper3 version `2`, manager `0x5c95…762b`, and quote `0x46ce…b15c`. Public ERC-20 reads identify that quote as **GMEB / GameStop, 18 decimals**, not USD or a verified stable asset.

The same-block calls to `tryBuy(token, 0, 10^16)` and then `trySell(token, estimatedAmount)` both returned ABI-shaped data. They are **not an economic round-trip**: the buy result reports `estimatedCost=18.264103043276783` GMEB but the supplied raw funds was `0.01`, and it returns `amountFunds=2^64`; this is incompatible with treating the call as a valid fixed-budget quote without further version/unit semantics. The sell call was also against the original fixed state, not the state after the hypothetical buy. No 5 or 20 USD figure is derivable.

**Four prerequisite:** verify Helper3 semantics for the listed token/version and prove a contemporaneous, causally observed GMEB/USD conversion. Until then `5USD_roundtrip=UNKNOWN` and `20USD_roundtrip=UNKNOWN`.

## Pons V2

The official [Pons V2 integration documentation](https://docs.ponsfamily.com/v2) defines deterministic curve quoting from `getReserves()`, `sellableTokens()`, `feeBps()`, `creatorTaxBps()`, and `currentSnipeTaxBps(recipient)`. It states that `getReserves` supplies pricing reserves, `sellableTokens` caps a near-graduation buy, sells close when `readyToGraduate`, and opening snipe tax is keyed to the **recipient**.

A fresh official-factory Blockscout `TokenLaunched` log supplied curve `0x25d3…EB41` and pair token `0xd060…9eec`. At fixed Robinhood block `0x3797972`, `getReserves()` returned quote reserve `16.64` and token reserve `1,000,000,000` in their respective 18-decimal raw units. ERC-20 reads identify its pair token as **NVDA / NVIDIA - Robinhood Token, 18 decimals**. This verifies that curve input and quote identity are observable; it does not establish USD economics.

The bounded probe did not call the remaining fee/sellability methods: the primary docs establish their required ABI, but the slice has neither a recipient to make `currentSnipeTaxBps` meaningful nor a current primary ABI artifact/selector for those functions. NVDA has no contemporaneous causal USD conversion in the local evidence. Therefore no buy/sell calculation, fee assumption, or 5/20 USD round trip is reported.

**Pons prerequisite:** same-block reads of all five official state inputs, including the actual intended recipient's snipe-tax value, plus a causal pair-token/USD conversion and a state-transition-aware quote. Until then `5USD_roundtrip=UNKNOWN` and `20USD_roundtrip=UNKNOWN`.

## Raydium LaunchLab

Official Raydium [bonding-curve](https://docs.raydium.io/products/launchlab/bonding-curve) and [PoolState account](https://docs.raydium.io/products/launchlab/accounts) docs show why list progress is insufficient. A launch can be constant-product, fixed-price, or linear; quote asset and decimals live in per-launch state. For a constant-product launch, correct math needs `real_base`, `real_quote`, `virtual_base`, `virtual_quote`, curve type and the configured buy/sell fee fields. Raw vault balances are not substitutes because pending fee counters can make them differ from `real_quote`. The transition to CPMM is a separate monotone status/migration boundary.

The existing LaunchLab list observer does not decode a verified `PoolState`, global/platform config, token-program fee extension, or quote-mint/USD conversion. Its API identity feed remains useful but supports no exact USD curve calculation.

**LaunchLab prerequisite:** verified per-launch state decoder and program ownership, curve-type/fee state, base/quote mint decimals and transfer-fee semantics, migration status, and causal quote-asset/USD conversion. Until then `5USD_roundtrip=UNKNOWN` and `20USD_roundtrip=UNKNOWN`.

## Small/safe observer decision

A **disabled, shadow-only** economics observer is technically plausible but is **not ready to implement now**. It must be per-protocol, operate once on an already-admitted identity, pin the queried block/receipt time, retain raw units and quote asset, and return `UNKNOWN` on every missing prerequisite. It must not feed entry, Paper accounting, or ordinary 4%/4% assumptions.

The minimum implementation order is: Four version/unit semantics plus conversion; Pons recipient-aware same-block state bundle plus conversion; LaunchLab validated state decoder plus conversion. Current evidence establishes protocol identity and selected state visibility, not economic coverage, alpha, or trade eligibility.
