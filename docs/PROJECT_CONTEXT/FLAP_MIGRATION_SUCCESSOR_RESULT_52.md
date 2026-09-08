# Flap official successor52 RESULT

REPLY_TO: C2C-20260909-FLAP-MIGRATION-SEMANTICS-52

Implemented and deployed 06b9fd7 through existing Paper launcher at approximately21:06:30Z. No reset, discovery expansion, new polling source/task, cost change or Live activation. Registration/activation/policy/funding/capital table hashes match pre-deployment evidence. Existing entry snapshots/cohorts retain original pool; ordinary forward exits append new ledger results.

## Verified protocol evidence

Official Portal BNB address and getTokenV6 layout/status enum independently checked. Fixed block0x732905d, chain56: all three return15 static words, status4(DEX), nonzero successor. Portal getter selector dbde08f0 verified with RPC web3_sha3. Original pool token0/token1 checks from49 agree with token identities. This resolves49's unknown proxy semantics through Portal; no V2/V3 interpretation of Flap proxy reserves.

- bsc:0x8554f3b4b657fc4df5ca00852accac9ce1c17777: 0x8faf52f55819900a37fd1f176f34b389489c9e1e → 0xdd7be2a957c14030bbbf88f1f698b5f448608a0b
- bsc:0x8e1cf10a02afb2f9803859278b7bc51bf1aa7777: 0xe5669cdc042ff451a6686bb57b2687859cf50cf0 → 0x120171d4268936017ff67ac8325bcff5867ecf20
- bsc:0xb726c0de859fb6b908435995e8eafc158d497777: 0xa09f13538321b973a8ae4f7b7bd8e0fe354e3be2 → 0xdff05f36140dd7e896bcad7e53326ae79ca443b1

Proof receipts stored insert-only through bounded script in existing KV (official-flap-successor/v1 keys); raw fixed-block response/header/blockhash plus evidence hash retained under data/research/flap_migration52/. KV itself is mutable infrastructure, not a cryptographically immutable registry; script does not overwrite existing links. No claim of independent migration-log confirmation or historical migration time: observed_at is the queried block timestamp and availability is current receipt record time, never backdated event discovery.

## Causal implementation

Held targets resolve authenticated successor; marks remain normal independently validated Dex USD price/liquidity. Original position/cohort pool remains untouched. Evaluator admits only successor observations strictly after proof recording; existing fresh-frame/floor/next-frame cost logic remains. Trigger evidence includes full proof and original/successor identities. Pre-existing pending exits rebase with proof and require a strictly later successor frame; settlement validates the same evidence. Unlinked/invalid state remains UNKNOWN, never inferred dead. Indicative valuation readers use the verified successor. No stable-quote assumption, synthetic price, copied historical quote or new RPC polling.

A standalone Dex HTTP probe returned403, so it supplied no market evidence. Current production per-pool Dex marks independently showed valid identities and USD liquidity (~5307/4588/4110) before deployment; actual exit used later natural production frames.

## Tests and runtime

10 targeted tests PASS (3 Flap cases,7 pre-existing pool-identity cases): authenticated post-proof two-frame exit, pre-link pending exit rebase, invalid receipt rejection, unchanged original cohort pool, unrelated pool rejection. Compilation and scoped diff check PASS. Independent review found pending-link handling and canonical-address pitfalls; fixed before deployment. Script emits lower-case ABI addresses; resolver rejects noncanonical receipts.

20 natural successor TIME_EXIT marks filled after deployment: BLEND6, ZDOG12, STOCKWORK2. All3 tokens now have0 open positions; historical already-closed positions are not counted as newly settled. This is Paper settlement, not an onchain sell or Alpha evidence.

Short runtime21:06:53Z: held_fetch p50 .7653s/p95 1.5092s,35 samples,failures0; held_apply_exit p95 .0473s; Dex PoolTimeout/connect errors0; passive drops0. /health running; /api/live Paper-only/Live locked. Existing costs4%/4%,floor1000 unchanged. Short window cannot establish long-run latency acceptance. Prior43 long-run test is historical, not a new post52 long-run claim.

Sources:
- https://docs.flap.sh/flap/developers/deployed-contract-addresses.md
- https://docs.flap.sh/flap/developers/inspect-a-token
- https://docs.flap.sh/flap/developers/token-migration

Evidence: probe.json, links.json, immutable_before.json, acceptance.json, live_post.json, performance_post.json in data/research/flap_migration52/. Other right-tail research remains separate and unfinished.
