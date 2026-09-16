# Migration-pool acquisition follow-up, 2026-09-17

## Retrospective evidence, not backfilled tradability

The frozen 94-key case artifact is `data/research/goal_cases205/cases_20260916T173845Z.json`. Nineteen matched tokens had more than ten minutes between their first persisted discovery exposure and first valid candidate-pool quote; 15 first quoted pools were provider-reported as created only after exposure. Four reported an earlier creation for that *same* quoted pool:

| Case | First exposure to valid quoted pool | Contemporaneous evidence | Attribution |
| --- | ---: | --- | --- |
| `solana:3nqHijNUExsnjNBb15WJsJ2xisyMVGN6FK4aUgZk1Rwj` | 33m58s | 28 Dex profile/update identity exposures, none with a snapshot; no in-window hydration-attempt records (attempt instrumentation started later). | Possible historical acquisition/attachment gap; no proof of the old queue state or early tradability. |
| `solana:6tRotGypA5QJKwmfgGFe4yp36eNQ4Vz7m8MNNpBnpYmq` | 62m25s | Migration hydration began 0.98s after exposure and returned in 2.61s, but selected a different Pumpfun curve with null liquidity. | Not an hour-long request queue. Target PumpSwap surface was not locally selected until later. |
| `solana:A9AHYeqb7nQk7LZUraw7rBCzYRjy2DRvE6NqWfFHKRdH` | 90m39s | Hydration began 2.18s after exposure and returned in 3.70s with a different null-liquidity curve. | Same alternate-surface limitation. |
| `solana:GY9mZfyPpxXxBXBxS2hB2XjhP3kfUsywTvgveozxpump` | 150m01s | Hydration began 5.47s after exposure and returned in 6.78s with a different null-liquidity curve. | Same alternate-surface limitation. |

The later quoted pools had positive recorded liquidity, but their creation timestamps and today's provider visibility do **not** prove they were available to the system or executable at first exposure. The historical provider response lacks an exact target pool ID; no hindsight buy or fill was added. The other 24/94 keys without current canonical matches and ordinary/failed controls remain open work.

## Current-code gap and bounded correction

The existing `DexScreenerClient.batch_quote` token-address endpoint can return multiple pools, but the primary snapshot selects one pool and ordinary hydration persists that selection. PumpPortal migration receipts contain the token mint and transaction signature, not an authoritative target pool address. The newer curve follow-up logic reused token-address batches every five minutes but stopped 90 minutes after the **selected curve's creation**. For a fresh migration of a much older curve it scheduled no follow-up; for a 64-minute-old curve it had only 26 minutes left. This is a current-code control-flow gap, not a claim that the historical runtime already had today's follow-up logic.

The active-curve branch now looks up only the latest locally received PumpPortal migration fact for that exact token, using the existing token/source-time index. The fact must satisfy `source_observed_at <= ingested_at <= recorded_at <= now`; invalid future facts do not mask valid earlier facts. A valid receipt can extend the existing follow-up deadline to at most receipt + three hours. The five-minute interval, active-trade prefilter, quote rejection behavior, 50% bounded follow-up reservation, 30-token per-chain Dex batches, and all normal safety/execution checks remain. No new source, API route, exact-pair request, strategy signal or buy authorization was added. Missing price/liquidity remains unusable for trading.

At the 2026-09-16 17:56 UTC read-only cross-section, 146 distinct tokens had a recorded migration in the preceding three hours; 133 had a latest snapshot, 18 latest snapshots still selected a Pumpfun curve, and only four also had null/sub-1000U liquidity plus at least three m5 trades. These are current-state counts, not a guaranteed future request ceiling; the existing scheduler quota remains the hard bound.

## Verification and limits

- Two new focused tests pass: old curve + fresh migration schedules receipt-anchored 5m follow-up and expires at three hours; absent/create-only/future-invalid facts do not extend it; the second observation uses the existing `fresh=True` hydration batch without re-enqueuing discovery.
- The existing fresh-snapshot follow-up test passes unchanged. An additional pre-existing capacity test fails in Store's unmodified reservation selection (`limit=10` includes non-pending rows although the test expects only pending); this stage does not claim the broader subset passed or change that unrelated queue behavior.
- Paper supervisor loaded only the edited runtime source, PID 106804 from 2026-09-16 17:56:53Z. `/health`, `/api/live`, `/api/performance` succeeded; same funding version, Paper=true, Live locked. Heartbeat advanced to 17:57:15Z and snapshot frontier from 972474 to 972791; historical position row count remained 38800. The previously held token had naturally closed by the final read, so no comparable held-quote age can be inferred from the post-deployment empty set.

Rollback is the local migration-receipt extension in `_shared_market_followup_schedule`; removing it restores the older curve-age horizon without altering already recorded evidence or account history. Natural migration-to-PumpSwap detection latency, API utilization under matched load, strategy entries and costed outcomes remain **pending forward observation**, not completed benefit claims. No scheduled research was enabled.
