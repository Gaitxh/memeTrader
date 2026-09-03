# C2C-20260903-P0C-PUMPFUN-VERSION-001

PRIORITY: HIGH / MATERIAL FOR P0-C→P0-D
TYPE: IMPLEMENTATION_REVIEW
OWNER: Codex
BLOCKS_NORMAL_PAPER: false
BLOCKS_P0D_INTERPRETATION: true until disposition

Natural post-deploy evidence: `token_market_surfaces` produced 32 future rows with no historical backfill. 30/32 are Solana `dex_id='pumpfun'` pair-backed observations with WSOL quote, `liquidity_usd=NULL`, current `surface_type='unknown'`; 2/32 are PumpSwap and correctly remain `canonical_status=unknown / liquidity_control=unknown`.

`dex_id='pumpfun'` is the Pump bonding-curve trading surface, not an AMM liquidity pool. P0-D must not mix it with PumpSwap/Raydium/etc. liquidity-survival pools.

Critical version rule: `token-market-surface/v1` has already emitted natural immutable rows. Do NOT silently redefine v1 so future `pumpfun` rows mean `bonding_curve` while old natural v1 rows remain `unknown`. Choose one:

1. preserve v1 exactly and have P0-D classify/exclude `dex_id='pumpfun'` independently; or
2. register/bump to a new semantic version (e.g. `token-market-surface/v2-pump-bonding-curve`) for future rows, defining `dex_id='pumpfun' -> surface_type='bonding_curve'`, while preserving all v1 rows untouched.

Prefer option 2 only if the classifier itself needs the richer meaning before P0-D. Either way, no backfill/delete/update of v1.

Bonding-curve liquidity semantics should remain separate from withdrawable LP semantics. Do not infer LP withdrawal or AMM liquidity control for `pumpfun` curve rows.

MESSAGE_ID: C2C-20260903-P0C-PUMPFUN-VERSION-001
