# Shared market cadence 184

## Diagnosis

The shared first-quote queue was fixed, but an ordinary pool's next scheduled
quote used `max(now + cadence, pool_created_at + 901 seconds)`. A valid pool first
seen during its first fifteen minutes was therefore denied dedicated follow-up
frames until minute fifteen. Strategies requiring three real frames could not
evaluate the most important early window unless an unrelated discovery surface
happened to repeat the token.

Official DexScreener discovery also ran every 30 seconds. Its four metadata
surfaces consume about eight requests per minute at that cadence, well below the
documented 60-request-per-minute class limit, while token hydration uses the
separate 30-address batch surface.

## Change

- Official Dex discovery now runs every 15 seconds by default.
- GeckoTerminal gap recovery remains on its independent 90-second rotation; it is
  no longer accelerated as a side effect of the Dex cadence.
- A valid original-pool quote schedules the next shared frame at:
  - pool age below 5 minutes: 15 seconds;
  - 5 to 30 minutes: 60 seconds;
  - 30 to 90 minutes: 5 minutes;
  - after 90 minutes: no dedicated lifecycle request.
- Active curve/no-price identities retain their separate five-minute graduation
  check and event-driven migration promotion.

At the configured three chains, hydration can start at most one request per chain
per five-second turn, or roughly 36 requests per minute, and each request carries
up to 30 addresses. First quotes remain ahead of follow-ups, held and pending-exit
market work retains higher transport priority, and generic historical retries stay
capped by stage 182.

## Verification

Fourteen focused discovery, cadence, retry, Gecko rotation, and shared-first-frame
tests passed. A new regression proves that a two-minute valid AMM schedules a
second frame at +15 seconds, allowing three observed strategy frames inside about
30 seconds without interpolation or replay.

This changes data availability, not historical decisions. Paper accounts, the
funding period, entry pool floor, original-pool exit/write-off rules, and Live lock
are unchanged.

## Forward checks

Measure discovery-to-first-frame latency, frame-2/frame-3 delays for pools younger
than five minutes, request rates by endpoint class, low-priority deferrals, held
mark age, evaluation latency, and trade conversion. If held/exiting work regresses,
reduce lifecycle follow-up allocation before reducing first discovery coverage.
