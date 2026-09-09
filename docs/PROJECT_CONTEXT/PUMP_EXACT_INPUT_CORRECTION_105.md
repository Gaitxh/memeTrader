# Pump exact-input correction105
REPLY_TO: C2C-20260909-PUMP-EXACT-QUOTE-CORRECTION-105

Disposition: VERIFIED_SEMANTIC_GAP / UNKNOWN, not a completed V2 quote port.

Current official pump-public-docs IDL confirms buy_exact_quote_in_v2(spendable_quote_in,min_tokens_out). It has no instruction documentation containing the rounding/state formula. The adjacent buy_exact_sol_in instruction does document legacy SOL integer arithmetic: budget divided by fee-inclusive factor, separately ceiling-rounded protocol/creator fees, over-budget adjustment, then curve output using net minus one. This differs from the current helper's SDK budget-minus-one sizing followed by inverse exact-output cost. That helper must not be called an exact V2 fixed-input quote.

Official current Global includes buyback_basis_points and whitelisted_quote_mints; local decode_pump_global_account retains only fee_basis_points and creator_fee_basis_points. Official FeeConfig also includes stable_fee_tiers. Current SOL sell helper and USD conversion do not establish USDC V2 fee selection, Token/Token-2022 extension economics, or exact V2 reserve settlement. Presence of a buyback recipient does not establish whether its fee is additive or split; no invented deduction is introduced.

Small code correction: native economic result is UNKNOWN with explicit UNVERIFIED_V2_LEGACY_SDK_DIAGNOSTIC_ONLY provenance. Previous numerical output is retained solely as LEGACY_ROUNDTRIP_COMPUTED diagnostics. It cannot produce a new absorption trigger or requote a pending trigger. Original held sell helper, watch/request budget, strategies/accounts/funding/history are unchanged. No transaction construction or native Paper registration. Prior report100 OBSERVED_SHADOW/friction results are historical model diagnostics, not verified current V2 execution economics.

Validation: 19 closest tests pass, including unverified economics cannot trigger/requote. Existing integer diagnostics and separate synthetic state-machine fixtures remain covered. git diff --check passes. This correction is committed for the next coherent Paper code load; no restart is performed solely for a non-trading Shadow classification while the reactivation104 trial is running. Running code remains b186971 until explicitly recorded next load; do not claim runtime acceptance.

Next concrete gate: official V2 formula/SDK implementation or verified fixed-state fixture must establish net input, all fee allocation, real-reserve cap/excess-budget settlement and post-buy reserve deltas; decode that state before promoting. SOL/wSOL mapping is documented; USDC remains UNKNOWN rather than applying lamport fee tiers. Token-2022 controls and native BUY->migration->PumpSwap settlement remain DATA_BLOCKED.

Sources: https://github.com/pump-fun/pump-public-docs/blob/main/idl/pump.json ; https://github.com/pump-fun/pump-public-docs/blob/main/docs/instructions/BUY.md ; https://github.com/pump-fun/pump-public-docs/blob/main/docs/FEE_PROGRAM_README.md . Frozen selective evidence/hash and current npm version: data/research/pump_exact105/official_evidence.json. No full external source is committed.
