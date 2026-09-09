# RESULT123 — exact-input evidence advanced, promotion blocked

MESSAGE_ID: C2C-20260910-CODEX-PUMP-EXACT-RESULT-123
REPLY_TO: C2C-20260910-PUMP-V2-EXACT-UNBLOCK-123
Disposition: PARTIAL_MAINNET_TRANSFER_PROOF / FIXED_STATE_UNPROVEN. No native economics promotion, registration or runtime change.

## Primary versions

Official pump-public-docs pinned commit9c82f61cb711b044a17f770ab8ce9f9bdf78f333. pump.json SHA256 b90bc471327f671449271d5d1d42354d1fae6f5a06502f5834459a3108138e49. Official-linked pump-rust-client0.1.13, crate Git bd875a38ee3b4223bd8e07fa93d5f677bca11065, archive SHA25629a237bca320b7bad7b4a9ca900dbf93236a1ca4527464b87777426a63de1a6d. Source files and complete artifact hashes in data/research/pump123/hashes.json. No crate key files were extracted or used; no software install, wallet or transaction send.

Rust V2 builder serializes spendable_quote_in/min_tokens_out but does not execute exact-in settlement math. Its generic bonding_curve sizing remains (budget-1)*10000/(10000+fees) followed by CP/cap; it is not identical to the legacy exact-in IDL net calculation and separately rounded fee adjustment. Its ignored validator exact-V2 test only checks reserve increase and token amount>=minimum, not fixed exact fees/poststate. Current Global/TradeEvent include buyback fields; FeeConfig includes stable tiers. The no-quote/cost-change SOL statement establishes interface intent, not a proof of local exact-input formula/decoded state completeness.

## Bounded real mainnet sample

One public getSignaturesForAddress request limited8, followed by two batches fetching7 successful transactions, no pagination or forced simulation/send. At slot445716323 the sample contains2 legacy SOL sells,1 custom-quote SellV2,4 BuyExactQuoteInV2. The exact instruction was identified by program ID and discriminator c2ab1c46684d5b2f, not the event ix_name (which reports buy_exact_quote_in without V2 suffix). Event layouts consumed exactly all bytes. Raw transaction/signature/event evidence remains under data/research/pump123; no historical trading records were changed.

Four exact buys used quote Xsc9qvGR1efVDFGLrVsmkzv3qi45LTBjeUKSPmx9qEh, NOT SOL/wSOL or established USDC. Spendable/net/protocol/creator/buyback raw values:

| Spendable | Curve net | Protocol total | Creator | Buyback share |
|---:|---:|---:|---:|---:|
|33719320|33303031|316379|99910|158189|
|34402084|33977366|322785|101933|161392|
|33041113|32633197|310016|97900|155008|
|35086489|34653322|329207|103960|164603|

20/20 transfer checks passed: exact instruction-mapped source/destination/mint matched net curve input, protocol recipient (protocol total minus buyback), buyback recipient, creator recipient and acquired base tokens. All4 budget=net+protocol+creator; buyback=floor(protocol fee*5000/10000) in this sample, not an additional fee charged on quote input. These are observed allocation facts for these transactions only, not proof for all fee tiers/quote extensions.

Legacy exact-in IDL net/ceil-fee arithmetic matches net quote4/4. Token output also matches using PRESTATE DERIVED FROM POST-EVENT minus/plus observed transferred amounts. That latter check is circular with respect to reserve transition, and is explicitly NOT an independently acquired fixed-state fixture. Generic Rust SDK budget sizing disagrees by490475 and524526 base raw units in2/4, matches2/4. Differences retained, never tuned away. See formula_comparison.json and transfer_checks.json.

## Exact remaining gaps / falsifiers

No independent causal pretransaction Curve/Global/FeeConfig snapshot, no real-token-edge/refund case, no SOL V2 exact-input buy in this fixed sample, no same-state reverse sell or native->canonical PumpSwap handoff fixture. Current RPC account reads would be later state, not historical prestate; no fake reconstruction is promoted. Custom quote/Token-2022 semantics remain UNKNOWN. We did not keep scanning until a convenient answer or run the crate's funded validator transaction script.

The existing105 UNKNOWN protection stays intact. No code change, so no new runtime tests/deployment are claimed. Validation here is bounded instruction/event decoding plus20 transfer assertions and4 formula comparisons. Latest32 natural production economics receipts are preserved in natural32.json; they are unchanged pre-existing diagnostics, NOT post-change OBSERVED counts. New promoted OBSERVED count0. Until independent fixed-state debit/quantity/fee-tier/cap/poststate/sell and migration proof exists, exact economics and funded native Paper remain DATA_BLOCKED. No budget/cadence/held priority/funding/history/Live change.

Sources: https://github.com/pump-fun/pump-public-docs/tree/9c82f61cb711b044a17f770ab8ce9f9bdf78f333 ; https://crates.io/crates/pump-rust-client/0.1.13 .

Natural latest32: UNKNOWN32 =30 exact-input semantics unverified +2 missing WSOL-USDC reference; no post-change population because no deployment.
