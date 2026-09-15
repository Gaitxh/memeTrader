# Discovery gap recovery 163 - 2026-09-15

## Observed failure

The user supplied 112 gold-token rows, resolving to 92 unique addresses. A read-only database
review at 2026-09-15 10:56Z found 75 token records and 17 addresses absent from `tokens`.
DexScreener's exact-address search still returned a current exact pool for 14 of those 17.
Three missing tokens had pools created on 2026-09-15 at 01:11Z, 04:15Z and 06:06Z, proving a
current discovery-coverage gap rather than only old history or a strategy rejection.

The configured GeckoTerminal new-pool recovery source was disabled after prior rate limits.
Native sources had no compensating backfill: the database records persistent Four.meme 403/RPC
failures and intermittent Robinhood RPC timeouts. DexScreener profile/boost surfaces are useful
but do not enumerate every unpromoted new pool.

## Change

`poll_multichain_meme_data_once` now rotates one GeckoTerminal network per 90-second shared cycle
instead of launching all configured networks together. A low-priority start is admitted only when
there is no critical exit and no queued high-priority Gecko request. Capacity deferral records the
discovery round as `interrupted`; it is not reported as a provider failure. The ignored device
configuration enables this recovery source. Live trading and funding are unchanged.

This is a forward coverage repair. The historical gold-token list is not injected into trading,
and no historical decision, fill or outcome is created.

## Forward acceptance

After the Paper restart at 2026-09-15 11:01:28Z, one complete rotation produced:

| Network | Returned pools | First local discoveries |
| --- | ---: | ---: |
| Solana | 20 | 11 |
| BSC | 20 | 7 |
| Robinhood | 20 | 20 |

All three rounds completed, with zero new GeckoTerminal 429 cases. All 38 new tokens received a
snapshot and an entry evaluation. Snapshot observation to first evaluation was 0.43-1.89 seconds
(median 1.24 seconds). The first-frame dispositions were 35 `entry_family_filter_rejected` and
3 `entry_pool_liquidity_below_configured_floor`; zero cohorts and positions were expected at this
early boundary and remain forward-monitoring work.

`/health` remained 200/running on funding period
`chain-meme-trader/funding-20260906-v002-final-1000`; `live.enabled` remained false. The focused
Gecko recovery and shared market microstructure tests passed (22 tests).

## Monitoring

The existing two-hour supervision loop should track new-pool discovery counts, snapshot-to-eval
latency, cohort conversion and source errors. Keep the recovery lane only while it remains below
the public host limit and does not delay exact-pool marks. A later profitability claim requires
settled forward cohorts; discovery coverage and low latency alone do not prove profit.
