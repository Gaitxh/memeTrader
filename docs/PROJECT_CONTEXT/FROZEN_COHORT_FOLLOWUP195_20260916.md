# Frozen cohort next-frame follow-up, 2026-09-16

## Observed break and denominator

Current Paper period: `chain-meme-trader/funding-20260906-v002-final-1000`.
In the fixed UTC window `[12:30, 13:40)`, the V6 evaluation ledger has 5,056
rejected evaluation rows covering 1,784 distinct tokens and zero admitted
evaluation rows. This is not 5,056 independent opportunities: 923 rows are
cohort observations and 597 are pattern observations. The window has two source
BUY fills, both from decisions made before this window. The largest explicit
refusal is `entry_family_has_no_policy` (1,622 rows/654 tokens), followed by
`entry_pool_liquidity_absent_curve_stage` (1,453 rows/1,000 tokens). No-policy
is a strategy-coverage gap, not evidence that those tokens were safe or profitable.

At this frontier 499 strategies are registered, 78 are not entry-paused, but
only `rw_quiet_reawakening_v1` participates in the ordinary V6 admission lane;
the other 77 unpaused arms are isolated cohort/pattern/native observers. This
explains ordinary `broad_launch`, `market_visible` and `flow_burst` no-policy
results. It is not an automatic reason to revive the old arms: active-period
market-visible variants collectively lost substantial Paper capital, and the
non-observer `mv_flow_demand_v1` and `mv_broad_demand_v1` realized -770.16U
across 121 closed positions and -346.75U across 53 respectively. Accounts share
token cohorts, so these are not independent estimates of market opportunity.

## Exact frozen-signal example

The natural `activity193_old_pool_tempo_v1` frame for
`solana:DKNGQFNGQmoBdXSRGKJ8tTu7uPDasw5JDcfMmWniNfow` was observed at
13:43:57.694Z and written as strategy-observer snapshot 941771 at
13:44:04.700Z. Evaluation 933196 persists `cohort_frozen_opportunity_ready`
with a 7.60x five-minute trade tempo, one-hour-old-or-more pool, 74 buys/22
sells in five minutes, 27,039.58U five-minute volume and 457,405.28U reported
pool liquidity. Its `ready_arm_ids` includes activity193. No later local
snapshot for this token or enrollment claim existed before this change. Thus
the 0 eligible-opportunity display was not evidence of 0 generated signals:
the signal awaited an independent next observation. Its pattern-watch membership
at that moment is not recoverable from the frozen evaluation, so the missing
frame cannot yet be attributed specifically to a watch-capacity refusal. This is one diagnostic example,
not a known winner. Its quote asset is another token (`ALLINU`), and the
reported pool/price do not prove a realizable two-sided fill or profit.

## Implemented bounded repair

Commit `7a94879` adds at most two valid, previously dispatched frozen cohort
identities per chain to vacant address places in an **already-due** low-priority
pattern-watch Dex batch. It never starts a new HTTP batch, exceeds the 30-address
request bound, or displaces held/pending-order priority. An empty signal,
undispatched signal, expired 60-second signal, or token already owned by the
watch/priority lane takes no place. This therefore addresses only the
unwatched-frozen-signal branch; it cannot repair a watched token whose due
request is deferred, fails, or yields no usable quote. The existing fresh Dex response, exact-pool
identity, as-of clocks, safety and next-observed Paper execution checks remain.
This is shared signal-to-data scheduling for all qualifying cohort arms, not a
strategy-specific market-data API.

`tests/test_shared_batch148.py`: 21 tests pass, including four new cases for
valid, undispatched, expired and priority-owned signals, plus the existing
unrouted-cohort shared-batch test. `git diff --cached --check` passed. The
existing Paper supervisor reloaded actual child PID 97364 at
13:54:23.103999Z; its loaded `runtime.py` SHA-256 matches the disk source,
499 policies and the funding period are unchanged. `/health`, `/api/live`
and `/api/performance` returned successfully; Live remains locked.

## Forward acceptance and limits

Historical 13:44 signal remains expired; no backfilled BUY or claim is allowed.
After deployment, a new natural `activity193` ready signal appeared at
13:58:00Z (evaluation 934353, observer snapshot 942919) for
`solana:Xs8S1uUs1zvS2p7iwtsG3b6fkhpvmwz4GYU3gWAmWHZ`. It was already
in the Solana pattern watch with frame_count 1 and next_due 13:58:08Z, yet
had no new local snapshot at 14:04:51Z. A separate read-only configured-proxy
Dex client returned that same exact pool in a 10-address batch, but this later
probe cannot prove what the runtime requested or received at 13:58. Runtime
Dex capacity then showed 5/5 low-priority requests active, 29 cumulative
connect errors and 19 low-priority deferrals. This demonstrates the present
fix is not sufficient for all missed next frames. The request/response/skip
reason for watched frozen signals remains an open P0 diagnosis; no historical
order is created from the later probe.
For new natural frozen signals, measure signal-to-follow-up request, actual
second-frame receipt and exact-pool match, safety disposition, source BUY,
closed net return and writeoff. Compare batch count, quote age and held/SELL
latency at comparable load. Engineering tests prove the bounded request rule,
not natural coverage gain or profitability. One diagnostic token and the
user-selected rising-token list must not become an entry allow-list.

Existing shared input already contains price, original-pool liquidity, volume,
buy/sell counts, pool age and limited buyer counts with as-of clocks. The
five low-cost feature ideas checked in this continuation mostly duplicate
existing trajectory features (buyer growth, participants per trade, depth-
supported momentum, volume/price divergence); signed dollar flow and wallet
clusters are not available. Do not add correlated global gates or an external
API for those ideas without independent forward value.
