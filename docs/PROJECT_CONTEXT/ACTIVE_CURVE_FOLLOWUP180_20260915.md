# Active curve-stage follow-up 180 (2026-09-15)

## Diagnosis

The umbrella `invalid_exact_asof_market_snapshot` label was decomposed from the
immutable source snapshots. In a bounded six-hour frontier, 3,326 of 3,337 rows
(99.7%) lacked a positive USD price and only 11 lacked `pairCreatedAt`; there were no
observed timestamp, identity, or h1/m5 ordering failures in that sample. The largest
surfaces were BSC Four.meme (2,600) and Solana Pumpfun (691).

A later rolling frontier contained 5,863 distinct curve-stage tokens. Only eight
(0.14%) later received a positive AMM frame, eight were re-evaluated, and one opened a
Paper position. Of 4,557 BSC curve identities, every hydration row was `hydrated`, but
only seven had another attempt after its first price-less rejection. The generic
hydration state therefore treated a valid curve identity as complete even though its
future migration was the decision-relevant event.

PumpPortal's explicit migration handoff correctly requeues fresh Solana migration
events, but it cannot cover BSC Four.meme or migration events the source did not
observe. Pattern-watch migration handling also works only after a token is already in
the bounded in-memory watch, whose admission requires a positive price.

## Change

`_shared_market_followup_schedule` now distinguishes an active curve identity from an
ordinary usable AMM quote:

- the pair must have a valid address, creation time, known curve-stage DEX id, and at
  least three current five-minute transactions;
- no-price or below-floor curve surfaces remain ineligible for trading;
- eligible curve identities reuse the existing follow-up half-batch every five
  minutes for the first 90 minutes and every 15 minutes thereafter;
- observation stops at the original six-hour lifecycle deadline;
- a migrated positive-price AMM returns to the existing one/five/fifteen-minute
  ordinary schedule and must still pass all identity, point-in-time, liquidity,
  safety, cash, concentration, and strategy gates.

No request ceiling or worker was added. In the measured six-hour frontier, only 147
curve rows met the three-trade prefilter. Even if all remained active for the complete
lifecycle, their upper-bound demand is about 15 follow-ups per minute, below the
capacity released by repair 179's consecutive-`no_pair` backoff.

## Verification and monitoring

Twelve focused tests passed across the new curve cases, repair 179 backpressure
cases, pipeline153 scheduling contract, and existing growth follow-up behavior.

Forward acceptance compares: active curve enrollments, curve follow-up attempts,
new-pool positive-price recovery, migration-to-evaluation latency, admitted cohorts,
deadline expiry, ordinary valid-pool lateness, first-hydration latency, provider
timeouts, and held-market cadence. Recovery is evidence of better coverage, not proof
of profitable alpha; economic results remain strictly forward and after costs.
