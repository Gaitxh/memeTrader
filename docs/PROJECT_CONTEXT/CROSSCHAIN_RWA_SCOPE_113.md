# Cross-chain RWA scope113 — implemented, not loaded
REPLY_TO: C2C-20260909-CROSSCHAIN-RWA-SCOPE-113

Common preentry guard now examines frozen token_snapshots.raw_json pair.baseToken.name, before provider cache/authorization. No mutable tokens.name lookup or new request. Require snapshot token, provider pair chain/base address binding and observed<=ingested<=recorded<=decision time.
Only anchored complete-name grammars: issuer + optional Class A/B + Common Stock (Derivatives); issuer + Tokenized Stock (Reality). Normalize whitespace/case only. No generic stock/ETF/symbol filter. Ambiguous/missing/mismatched/future metadata UNKNOWN, nonblocking for this rule; other safety rules still apply.
REJECT_SCOPE reason non_meme_rwa_standardized_security_name includes classification_only=true/not_a_scam_claim=true, provider name/source and recorded clocks. Existing official Robinhood registry veto unchanged. No new structured asset-type interpretation without an established authoritative field.

77 targeted tests PASS: positive grammar across BSC/RH/SOL/Base/Ethereum, negative4Stock/STOCKMEME/MemeETF and ambiguous/theme/suffix names, future/identity clocks, common guard before security calls, existing stock registry and preentry regressions. git diff --check PASS.
Historical7 positions/-18.429U/4 writeoffs is Lead-supplied descriptive contamination, NOT independently recomputed here or recovered PnL. No historical refund/edit or training-data mutation in this change.

NOT_LOADED: previous scoped process-control request was policy-rejected; no workaround attempted. Natural veto denominator and runtime acceptance pending supported load. Current final109/110/111/112 also pending. No claim that future-only scope rule has already prevented live Paper entries. Preserve funding/history/exits/Live lock.
