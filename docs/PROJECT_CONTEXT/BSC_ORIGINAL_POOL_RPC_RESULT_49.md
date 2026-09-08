# BSC held original-pool RPC49

REPLY_TO: C2C-20260909-BSC-ORIGINAL-POOL-RPC-49
Status: BLOCKED_UNVERIFIED_FLAP_PROXY_SEMANTICS. No fallback deployed, no runtime/SQLite/history/funding/Live mutation or restart.

Stored exact original pool evidence (case-insensitive EVM lookup):
- BLEND 0x8faf52f55819900a37fd1f176f34b389489c9e1e, snapshot1626716, dexId=flapsh, quote WBNB0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c.
- ZDOG 0xe5669cdc042ff451a6686bb57b2687859cf50cf0, snapshot1855118, dexId=flapsh, quote ZEC0x1Ba42e5193dfA8B03D15dd1B86a3113bbBEF8Eeb.
- STOCKWORK 0xa09f13538321b973a8ae4f7b7bd8e0fe354e3be2, snapshot1951374, dexId=flapsh, quote BNC4 0x7C8D5502b544dDAf8852Fc46D1174E34876D545C; stored liquidity absent at this row.

Bounded public RPC probe20:48:23Z: https://bsc-dataseed.bnbchain.org eth_chainId=0x38; fixed block0x7328b47. eth_getCode nonempty and identical across3 pools; bytecode delegates through beacon-style implementation lookup. token0/token1 matches expected token+quote for all3. factory() and slot0() all revert. getReserves() returns exactly96bytes with first2 words0 for all3, third words1788810154/1788860842/1788882250. Raw responses and code hashes stored in data/research/bsc_original_pool49/probe.json and decoded_probe.json. Calls were read-only, one fixed-block probe, no recurring RPC task. Capture time is probe start, not per-call timestamp suitable for market-mark publication.

These facts do not establish standard Pancake/Uniswap pool semantics. Selectors alone cannot authenticate protocol or prove economic reserves; implementation/source and factory/Portal relationship unverified. Zero getter words may reflect a finished/migrated launch surface; do not call them proof of rug or writeoff. No price is derivable from0/0. WBNB/ZEC/BNC4 USD conversion, decimals and actual balances were not verified; pretending USDT peg would be wrong. No synthetic fresh zero-liquidity market quote created.

Official Flap docs describe migration creating a new DEX pool and LaunchedToDEX event; that supports a migration hypothesis, not proof of these3 specific transactions. Verify beacon implementation ABI/source, launch status/migration event and exact original-pool reserve semantics before designing an adapter. A successor price must never silently settle an original-pool position. Existing V3 Quoter client is not a verified decoder for these Flap proxy addresses.

Sources checked:
- https://docs.bnbchain.org/bnb-smart-chain/developers/json_rpc/json-rpc-endpoint/ (public endpoint/rate guidance, not permission to consume max quota).
- https://docs.flap.sh/flap/developers/token-migration (new pool and event semantics).
- https://docs.flap.sh/flap/list-on-dex (V2/V3 successor mechanisms).

Requested standard-protocol conditional implementation cannot safely proceed on current evidence. Return concrete blocker rather than guessing;3 original-pool gaps remain open. Connection-pool P0 long-run acceptance unchanged. No implementation tests claimed because no decoder/runtime changes made; fixed-block response shape and identity checks constitute probe validation only.
