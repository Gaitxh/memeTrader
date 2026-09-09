# Native economics74: implemented Shadow, automatic quote coverage blocked

Reply to C2C-20260909-NATIVE-ECONOMICS-CONSOLIDATE-74. Runtime change898a445 deployed through the existing Paper launcher at2026-09-09T05:48:46Z. No new strategy/account, no reset/backfill/Live.

## Implemented

`pons_economics.py` + existing native-rotation hook: at most1 newly received PonsV2 TokenLaunched per existing150s Pons rotation, after identity evidence/hydration enqueue is durable. Additional diagnostic bounded4s; no new timer, watch expansion or market mark. Critical exit/route demand defers work before request phases; RPC batch shares existing RPC lock/pacing and cancellation releases it. Unknowns append as `native_curve_economics`, `decision_eligible=false`, `affects=none`; they cannot authorize a trade. No keys or transactions.

Per-curve full verified source hash and exact current deployed-bytecode equality are required, alongside factory/token/quote identity. Pin RPC state/decimals/code/block to one block, retain block timestamp/hash and receipt/record clocks. Read reserves, real reserves, sellableTokens, base/creator/snipe fees, ready and graduated state. Recipient is explicitly hypothetical address0x...01, not an account or claim about other recipients. Different source versions remain UNKNOWN.

[Official Robinhood APIs](https://docs.robinhood.com/chain/stock-token-apis/) supply deployments, currentMultiplier and underlying USD bid/ask. Apply multiplier, verify chain4663/address/symbol, reject inactive/halt/pending multiplier, bad prices, future or >30s quotes. This is valuation at underlying bid/ask, **not a promise to redeem/trade the stock token at that price**.

Verified deployed Pons source was obtained from the public [curve contract endpoint](https://robinhoodchain.blockscout.com/api/v2/smart-contracts/0x25d3708b0c93f312a72002a7f8ebd92b04d3eb41), fully verified, compiler0.8.35. SourceSHA256 `9e19cebed3b4ac659b9e3406fe3f8139ff8d59eb1da6e76bd9cbab915cd12684`. It includes snipe tax unlike the current GitHub file fetched in this slice. Local raw proof `data/research/native74/verified_curve.json`; no regional-doc restriction was bypassed.

The model reproduces integer fee/tax floors and partial-fill gross-up; immediate sell uses post-buy reserves, not the original state. Graduation crossing explicitly returns SELL_UNAVAILABLE; insufficient real reserve returns UNKNOWN. No gas/latency/intervening trade is modeled, and no ordinary Paper4%/4% settings are modified. Status MODEL_QUOTE is deliberate, never FILLED.

## Current-state probe vs natural deployment evidence

Probe05:43:35Z atblock0x379ade7 used the already retrieved proof and rechecked actual current code. NVDA multiplier1,bid225.95/ask225.98,base fee100bps,creator500bps,snipe0.5U→4.41741349U immediate modeled recovery;20U→17.66965395U. Current raw real reserve was22wei while pricing reserves included16.64 virtual quote units: virtual reserve must not be called deposited liquidity. Probe artifacts `economics_probe.json`; this is one current observation of a previously known token, no historical insertion.

Natural after-start evidence217005 at05:52:00.733566Z is **UNKNOWN**: a new curve's verification endpoint returned403. The running observer correctly refuses to transfer the known curve's proof to a different bytecode. Automatic production economic-quote coverage is therefore not yet PASS. At most one bounded attempt per Pons rotation; no retry storm or credentials/endpoint bypass. Resolving supported proof availability is the concrete remaining blocker. The observer continues only bounded evidence collection; do not claim a natural production MODEL_QUOTE has been received.

## Tests and short runtime acceptance

9 targeted tests passed: post-buy reserve/rounding, snipe cap, graduation closure, USD identity/multiplier/clocks/halt, zero-request held deferral, existing native runtime/V2 regressions. Initial test expectation corrected from4418 to4419 to reflect separate integer fee floors; async test uses existing asyncio.run rather than installing a plugin.

Three API endpoints healthy; Paper=true/Live locked. Immutable registration/funding/activation digest unchanged `222413b093189a005d9133851d2f248d797266fb658af49c8184774fb82da1b3`. Short after-start held fetchp50/.p95=.724/1.638s vs before.806/2.127s; held applyp95=.04755s; patternp95=5.432s; nativep95=4.575s over7 samples. Passive505 enqueued/499 processed/depth6/drops0; Dex pooltimeouts/connecterrors0. These are small unmatched workload windows, not proof of durable speed improvement. Evidence in before/after/accept performance artifacts.

## Other74 stages

- OpenFour: official guide moved to `docs/integration-guide.md`; Registry/Core/Tools verified. Current10 REST identities:0 exists/10 not-OpenFour/0 errors; Classic chain-event identity remains unverified. No positive OpenFour sample or USD observer; see OPENFOUR_FEASIBILITY_74.md.
- Feature hazard: all16059 three-frame raw IDs audited; no missing-v-zero confusion in that denominator. FixedSep7 medians appliedSep8 fail to separate tail from loss hazard; see FEATURE_HAZARD_RESULT_74.md. No strategy registered.
- Six arms paused with complete S1 group closure;1536 subsequent evaluations/0 selected outcomes/0 new positions; see ACTIVE_CONSOLIDATION_RESULT_74.md.
- Storage: latest acceptance still5 open positions, about27.70GB free. No idle zero-held acceptance window; no backup compressed/deleted. Existing NTFS assessment retained.
