# Round 189: Sellability gate and original-pool quote recovery

## Scope and evidence

- Paper only; current period `chain-meme-trader/funding-20260906-v002-final-1000`. No funding reset, Live activation, historical quote replay, or automatic strategy promotion.
- All ordinary Paper arms use the shared `PreentrySafety` gate. The opt-in 152 DEX-continuity path previously accepted a market proxy despite absent security evidence. The native Solana curve arm has separate verified mint controls and an immediate model sell-back check.
- In a recent fixed receipt window, 23 BSC safety authorizations based only on `cannot_sell_all=false` preceded 65 Paper positions; 13 Robinhood authorizations based only on `honeypot_with_same_creator=false` preceded 30 positions. This demonstrates an overly permissive authorization rule, not 95 proven honeypot losses.
- Current-period audit: 38,290 positions, 1,384 tokens, 8,967 distinct entry snapshot IDs. None of 8,966 readable entry snapshots contains a persisted affirmative honeypot/non-sellable/100% sell-tax fact; one native ID is not a token snapshot. Across 35,465 preentry safety receipts, six explicit honeypot receipts concern three BSC tokens, and none joins a current-period position. Thus there is **no evidence-qualified position to reimburse or void now**. Ordinary pool write-offs and missing safety reports are not honeypot proof.
- Original-pool stale case: `solana:EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm` in pool `Hy5eSz9HicuFZhEZEkqSJfLMZRTnywwkUGEo5742FnbS`. DexScreener's exact-pool response reported the held token as quote, without USD price or liquidity. GeckoTerminal's exact-pool response exposed `quote_token_price_usd=0.176661255963878` and `reserve_in_usd=5109.8290882654`, while its base USD price and base/quote ratio were zero. The parser had discarded the direct quote-side USD price. A different WIF pool is not a valid substitute.

## Changes

- EVM BSC/Robinhood buys now require a direct, non-honeypot or sellability fact from the existing GoPlus/Honeypot.is security acquisition. Low taxes, other normal flags, and `cannot_sell_all=false` alone do not authorize. Affirmative risk still vetoes even when another field is clear.
- Solana buys require every existing token-control field to be explicitly clear; a present transfer hook vetoes. No new provider or request was added.
- The opt-in DEX-continuity arm retains its market-continuity condition but can no longer substitute it for absent sellability/control evidence. Known current and cached hard vetoes carry through.
- The GeckoTerminal normalizer keeps positive `quote_token_price_usd`; the held-pool adapter can value the held quote token using that same exact pool's direct USD value and reserve. Wrong identity, stale receipt, insufficient/missing reserve, or invalid price remain rejected. This is indicative Paper pricing, not a guaranteed executable sell.
- Existing append-only `void_chain_meme_trader_positions` is the authorized remedy when a BUY's full lifecycle is proven honeypot-affected. It excludes the lifecycle from effective cash and PNL, including prior credits and profits, while retaining raw trades and evidence. It is idempotent. No void was applied without an affected BUY ID and direct proof.

## Verification and forward check

- Focused regression: 60 tests passed across safety, opt-in proxy, exact-pool quote, and whole-lifecycle account void. The account fixture includes a profitable sale, a loss, a partial/open position, a prior credit, and retry; cash returns to 1000U and realized PNL to zero for the voided arm, while another arm remains unchanged.
- Post-deployment service, quote-age, and natural same-pool recovery are recorded separately below; a unit test does not establish that the public provider has refreshed the real position.
- Review newly authorized buys by chain and safety fact, and any explicit honeypot receipt against current positions. Void only confirmed affected BUY IDs with source receipts; do not refund unknown, ordinary losses, or vanished pools under the honeypot label. Compare held quote age and fallback provider failure over a comparable load window before changing API pace.

## Deployment readback (2026-09-16 08:55 UTC)

- Paper supervisor relaunched runtime child PID 67704 without restarting Web or resetting the funding period. `/health`, `/api/live`, and `/api/performance` returned success; `/api/live` retained Paper-only, Live locked, and the same period. The heartbeat advanced after restart.
- The WIF exact original-pool mark remained expired after deployment. `source_health` showed GeckoTerminal exact-original-pool HTTP 429 at 08:54:44 UTC; DexScreener's exact response still lacked usable price/liquidity. The configured CoinGecko Demo exact-pool fallback reports `missing_api_key`. This is an upstream availability limit, not a license to use a different pool, a stale quote, or a fabricated write-off.
- The new parser/adapter is deployed and focused tests pass, but natural WIF recovery is **not yet observed**. The existing bounded retry path will use a fresh same-pool response when the free endpoint allows it. Continue treating this position's executable value as unavailable until then.
