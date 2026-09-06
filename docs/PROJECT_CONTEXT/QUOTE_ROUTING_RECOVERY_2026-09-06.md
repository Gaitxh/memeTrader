# Jupiter fixed-slippage routing and recovered source incidents

## Observed fault and correction

On 2026-09-06 the shared WSOL reference recorded intermittent
`JupiterQuoteProtocolError` (case 78). Two read-only WSOL/USDC probes used
1,000,000,000 input raw units, requested 400 bps and supplied no taker:

- Metis returned 400 bps and a minimum of 96% of output.
- Excluding Metis returned JupiterZ with 0 bps and minimum equal to output.
- Both were quote-only responses without a transaction. This is a routing/cost
  contract mismatch, not evidence of a missing Token pool or an unsellable coin.

The client now excludes JupiterZ only for positive fixed-slippage requests.
It retains the requested-slippage, identity, amount and transaction checks;
it does not synthesize an upstream minimum or accept a zero-cost quote as 4%.
Zero-slippage callers retain their previous router selection. WSOL error reports
also retain the client's local validation reason, without keys or raw responses.

Reference: [Jupiter Swap V2 Order API](https://developers.jup.ag/docs/api-reference/swap/order).
The API documents quote-only calls without taker and the `excludeRouters` parameter.

Nine focused test cases passed: routing at 0/100/400 bps, normalization, mismatched
identity/slippage, transaction rejection, no-route classification, price-impact
units, shared-reference scheduling and safe protocol details/stale-reference expiry.
Paper was restarted through its existing launcher at 17:47:10 +08:00; the Web
process, funding period, positions, trades and all 188 strategies were preserved.
Natural source recovery is checked separately from those tests. This change does
not guarantee upstream availability or eliminate every possible protocol failure.

At 09:48:01 UTC the deployed WSOL reference produced a new successful item;
the latest trade was 418444 at 09:47:41 UTC and `/health` reported running in
the unchanged `funding-20260905-fixed-1000` period. At 09:48:54 UTC cases
58/60/61/62 and the repaired routing case78 were updated with individual evidence
and this report link. Active original-pool rate-limit cases were not closed.

## Source incident status semantics

Cases 58, 60, 61 and 62 describe earlier capital-quote timeout / GeckoTerminal
new-pool rate-limit incidents. Mark an individual case recovered only when its
same-source successful item is later than that case and it has not recurred for
at least ten minutes. Use the existing `fixed` status with an explicit recovery
note, not a claim that rate limits can never recur. Existing re-opening on a new
occurrence remains active. Current original-pool 429 incidents remain open.

This report authorizes no historical trade cancellation, refund or account reset.
The user has explicitly skipped those operations for this stage.
