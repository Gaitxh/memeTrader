# Shared discovery and market core 181

## Diagnosis

The free API capacity was not the limiting factor. DexScreener already supports up
to 30 token addresses per quote request, but the runtime selected 30 rows globally
and then split them by chain. Recent requests averaged only 7.63 addresses. First
quotes also shared a fixed reservation with lifecycle follow-ups, while four
undocumented WebSocket loops duplicated the official HTTP discovery surfaces.

In the recent bounded sample, discovery-to-first-Dex-frame latency was p50 308s and
p90 325s. A successful hydration frame was persisted but did not directly enter the
shared strategy observation input, adding another queue before strategies could see
data the system already had.

## Change

- First quotes now consume hydration capacity before 90-minute follow-ups; follow-ups
  fill only spare addresses.
- Each chain can fill one 30-address batch per hydration turn.
- A newer discovery receipt immediately promotes prior `no_pair` and `error` tokens.
- Every valid hydrated Dex frame is broadcast to the shared strategy input at once.
- The four undocumented Dex WebSocket loops are no longer started. Official HTTP
  surfaces remain the discovery path and run every 30 seconds by default.
- Existing Pump/native launch discovery remains for pre-pool/new-token leads.

All strategies share the resulting token snapshots. Multi-frame history remains
available to strategies that need it, but it is no longer required before a broad or
fast strategy can receive the first valid frame.

## Preserved contract

Paper-only execution, independent strategy cash, exact token/original-pool identity,
point-in-time timestamps, positive finite prices, the configured entry pool floor,
and pre/post-exit pool write-off behavior are unchanged.

## Forward checks

Compare 15-minute windows after deployment using discovery-to-first-frame p50/p90,
first-quote queue age, addresses per batch, `no_pair` share, transport failures, and
first-frame-to-entry-evaluation delay. Strategy profitability remains a forward
outcome, not a release claim.
