# Pump create first-quote recovery, 2026-09-16

## Verified break and denominator

Strict first-local-discovery window `2026-09-16T11:15:00Z` through
`11:25:00Z`, inclusive, in the current Paper database: 231 unique token IDs;
129 had a later `token_snapshots` row and 102 had none as of the read at about
12:10Z. A previous loose-window/query-time report stated 233/126/107. The
five-token discrepancy is a definition/read-time difference, not evidence of
five dropped orders. None of these counts is a pool, signal, order or fill count.

All 102 missing-snapshot IDs have `token_detail_hydration.status='no_pair'`
and a recorded Dex hydration `no_pair` exposure. The first no-pair receipt was
within 30 seconds of local discovery for all 102; 99 currently have one
hydration attempt, three have three. Their original discovery sources are 79
`pumpportal:create`, 13 `raydium_launchlab`, one Pump migration, six Robinhood
Pons and three BSC four.meme. Thus first-attempt queue starvation and HTTP
error are not the explanation for this exact 102-ID slice. `no_pair` means the
Dex batch did not yield a usable matching pair; it does **not** establish that
no market existed anywhere, nor distinguish an unindexed pair from an
identity-mapping miss. This is a data-coverage diagnosis, not a profitability
claim or retrospective buy signal.

`mark_token_detail_hydration` already schedules a recent Pump-create no-pair
retry at 90 seconds and, after another miss, at 210 more seconds. However the
shared batch selector filled its capacity with hydrated follow-ups and pending
first quotes before taking general no-pair retries. Under persistent discovery
load, those scheduled retries could remain unserved. This explains why 99 of
the 102 had only one attempt despite being far past their first due time.

## Implemented change

Commits `0161b27` and `faa79f1` reserve up to two already-due, recent
Pump-create `no_pair` retries per chain in the existing Dex hydration selection.
A batch of at least ten places takes the newest due and oldest due; a smaller
batch takes only the newest due. This applies only in the `prefer_fresh`
per-chain lane, only to attempts 1 or 2 with a launch fact and next-attempt
timestamp within the previous ten minutes. It also works during the slower
generic-retry cooldown. Slots are deducted from pending capacity; held/SELL
quote priority, API source, batch size,
strategy policies, safety, execution, accounts and earlier observations are
unchanged. If a chain otherwise has no query work, servicing the retry can
still produce a batch; this change does not promise a fixed HTTP call count.

The first candidate query scanned a 500-launch-fact tail and cost about
40-55 ms per chain on the live 19 GB database. It was replaced **before
deployment** with the existing `(status,next_attempt_at,enqueued_at)` index
range plus an indexed launch-fact existence lookup. Direct query timing was
about 0.02-0.7 ms per chain after warmup. The whole due-selector remains
roughly 170-200 ms for Solana under the observed load, so this is not a claim
that overall scheduling has become fast; compare equivalent loads and profile
other branches before further tuning.

Five focused `test_shared_market_retry182.py` tests pass, including saturated
pending queue, disabled generic retry, before-due exclusion, second due retry
and newest/oldest balance. A wider shared-selector run had 11 passes and one older assertion
expecting a generic old no-pair retry to consume a reserved slot even with
seven pending rows; the current intentional pending-first behavior predates
this Pump-specific branch. Another growth-follow-up test fails with
`prefer_fresh=False`, where this new branch is inactive. These are **not**
recorded as a full-suite pass; no unrelated test assertion was rewritten.

## Deployment and next evidence

The Paper supervisor restarted only its trading child for each commit. The
final two-slot runtime PID 80372 started at `2026-09-16T12:22:10.750246Z`,
with 499 registered arms and a `store.py` source hash matching disk. The period remains
`chain-meme-trader/funding-20260906-v002-final-1000`; `/health`,
`/api/live?view=summary` and `/api/performance` returned 200. The summary
reported `paper_only=true`, `live_locked=true`, 4% adverse slip on both sides
and a 1000U original-pool floor. Snapshot frontier at initial verification
was 934797 and advanced to 934853 on the next read. No account reset,
historical fill rewrite, new API or recurring
review was performed.

In the first runtime interval, about 73 recent Pump-create no-pair retries
were already due. One earlier token, `7oWX...pump`, naturally changed from
Dex `no_pair` to a later Dex snapshot on its second attempt. That snapshot's
liquidity is missing, so it is **not** a qualifying original-pool quote or a
Paper entry. This is one delivery observation, not an economic result. The
one-slot version favored older due retries and did not yet retest the newly
discovered 12:15-12:16 cohort; this prompted the two-direction correction.

At a bounded read at `12:25:38Z`, 12 post-final-activation Pump-create tokens
enqueued by `12:23:10Z` had four natural second Dex attempts. Their first
no-pair to second-request gaps were 95.0-103.7 seconds. Each second request
persisted a Dex price snapshot, but all four had `liquidity_usd=NULL` and
therefore **zero qualifying 1000U original-pool quotes** in this observed
subset. The other eight are censored at this read, not classified as
permanent misses. This confirms retry delivery, not a new BUY, exit or net
profit. A pool may appear later, and the continued lifecycle must be read
as-of its later receipt.

The old 102-token window was already older than the ten-minute fast-retry
boundary by deployment; this release must be evaluated on **new** Pump-create
cohorts after startup. Measure independent token IDs with first Dex no-pair,
percentage retried within 90-second due time plus dispatch lag, second-frame
valid original-pool quote rate, 429/errors, new-first-quote latency, held and
exit freshness, then source BUY, Paper exit and net cost-inclusive results.
The hypothesis can fail: many create mints may genuinely have no qualifying
DEX pool, and early retry may yield no extra tradable opportunities.

Official capacity and response fields: [DEX Screener API reference](https://docs.dexscreener.com/api/reference).
