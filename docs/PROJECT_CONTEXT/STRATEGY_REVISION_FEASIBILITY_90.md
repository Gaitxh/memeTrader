> SUPERSEDED P1-A: 90-ADDENDUM-A withdrew checkpoint sales and new enrollment.
> See CHECKPOINT_WITHDRAWAL_90A.md. Earlier deployment details below are historical.

# Message90 strategy mechanisms and boundaries

The user authorizes two additive5U/max4 Paper exit challengers, directly against
resource_age_rate_candidate_v1, preserving parent entry/exit/history. Implementation
and tests are in age_rate_revisions.py, test_age_rate_revisions.py and
 test_age_rate_revision_store.py. No independently funded duplicate control.

## Checkpoint runner

At the first causally usable >=15m checkpoint, economic value means actual realized
proceeds plus the remaining position sold under current sell_terms. It does NOT
mean realized proceeds alone. Exit if value is below original debit OR both price
and liquidity declined across strictly causal adjacent frames within60s. If covered
and no such deterioration, continue parent. Missing structure remains UNKNOWN and
awaits another frame, while all parent stops remain active. No future peak, chain,
date, or fitted profit threshold. This changes the old unconditional15m horizon.

## Dynamic principal recovery

Copy age-rate entry and all parent exit protections. Earliest current observation
where a strictly partial sale can cover unrecovered original debit triggers review;
there is no inherited +80% trigger or fixed60%/50% sale. At the next valid pool frame,
recompute the minimum synthetic raw amount via sell_terms, including fees/slippage.
If not partially coverable then cancel only this recovery attempt. Actual fill
proceeds alone set principal_recovered; only after that fill reset high-water.
A near-break-even partial may sell almost the whole position, leaving a tiny runner.
This limitation is reported rather than hidden by an unrequested profit threshold.

## Pump.fun/Solana native entry: DATA_BLOCKED

Existing bonding_curve_identity derives mint-bound Pump PDA. Confirmed RPC decoding
has virtual/real reserves, total supply, completion, creator and quote mint. Active
PregradWatch records bounded real-reserve observations (not gross trade flow).
Existing pump_bonding_curve_sell_quote_v1 is fee-aware integer SELL math for supplied
remaining_amount_raw. bonding_curve_quotes validates curve/Global/fee-config accounts,
source hashes and fee tiers; it supports held-position current-surface recovery.

This does not yet supply a complete new-entry same-frame buy debit plus paired
post-buy sell quote, WSOL-to-USD conversion and all native network/transaction costs.
The present watch calls observations, not a complete economic quote. Therefore
pump_native_absorption_v1 is NOT registered as Paper. Existing pregrad evidence stays
Shadow; no unverified economic score is promoted. Pons403 is unrelated to this Pump
finding. Complete native economics is the explicit remaining data boundary.

Validation is engineering only. New natural common-fill outcomes must compare each
challenger with the deployed parent, not just with the failed60m challenger. No
profitability or reduced rug risk is established by these tests.
