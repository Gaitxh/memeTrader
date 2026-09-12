# ROUND 120-28 RECORD — the capital/concurrency hypothesis is closed; a consolidated bottleneck statement

Date: 2026-09-13
Epoch: `chain-meme-trader/funding-20260906-v002-final-1000`
Mode: paper (`live.enabled=false`). **Read-only round; no production code changed.**

## 1. The last unexamined hypothesis

The user's core complaint is that too few tokens reach judgement and entry. Rounds 20–22 and 25–26
examined observation capacity, processing speed, arm redundancy and token-level selection. One
explanation had never been tested: **that the account is out of usable capital, or that
concurrency / per-arm risk limits are saturated**, so a fired signal cannot become a position.

It is not. Measured:

| check | result |
|---|---|
| `capital_eligibility` | `per_strategy_account_independent` |
| `starting_cash_usd_each_arm` | **1000.0** |
| registered arms | 325 |
| nominal capacity (arms × 1000U) | **325,000U** |
| deployed in open positions | **4,400.00U** (220 positions) |
| **utilisation** | **1.35%** |
| idle | 320,600U |
| positions an arm could hold at 1000U / 20U | **50** |
| observed max open on one arm | **8** |
| `max_open_positions` | 0 (unlimited) |

**No entry was ever refused for a capital reason.** The entry-evaluation distribution has exactly
8 distinct reasons, and none is capital-, cash-, limit- or concurrency-flavoured
(`cohort_observation`, `no_active_matching_entry_policy`, `pattern_observation`,
`entry_pool_liquidity_absent_curve_stage`, `invalid_exact_asof_market_snapshot`,
`entry_pool_liquidity_below_configured_floor`, `entry_pool_liquidity_unknown`,
`entry_snapshot_too_old`).

**The one global throttle that could still have bound is empty:**

| table | rows |
|---|---|
| `chain_meme_trader_order_intents` | **0** |
| `chain_meme_trader_execution_attempts` | **0** |
| `chain_meme_trader_execution_results` | **0** |
| `chain_meme_trader_quote_attempts` | **0** |
| marks with `status='PENDING'` | **0** |

`max_pending_buy_intents = 8` is a global cap, so it *could* have throttled a burst of buyers —
there is no evidence it ever has: nothing is queued and no attempt was ever deferred.

## 2. A useful side-number: the fill layer sees 37 tokens

468 fills across **37 distinct tokens**, spawning 2,506 positions — **5.36 positions per fill**.
That is the cohort replication of round 25 seen from the execution side, and it confirms that
token breadth is set upstream at the signal/observation layer, not at execution.

Trades: BUY 2,506 · SELL 1,600 · WRITEOFF 764.

## 3. Consolidated bottleneck statement

Every link of the chain has now been measured. What binds and what does not:

| link | measured status |
|---|---|
| discovery | healthy — 10,089 tokens discovered |
| collection | healthy — 94.5% of discovered tokens observed |
| feature/trajectory | healthy — 66.8% of accepted observations form a ready 30 s window (r21) |
| **observation capacity** | **THE BINDING CONSTRAINT** — ~30 dense slots; 0.4% of observed tokens ever entered (r20/r21) |
| processing speed | not binding — observed snapshot → position p50 **0.18 s** (r20) |
| freshness rules | not binding — `entry_snapshot_too_old` is 0.03% of evaluations; limit is 90 s |
| signal generation | not binding — mechanisms fire amply |
| arm fleet | not redundant (311 distinct contracts) and not prunable (r25) |
| **capital** | **not binding — 1.35% utilised** |
| concurrency | not binding — 8 of 50 possible per arm |
| pending-intent throttle | not binding — all queues empty |

**The single binding constraint is how many pools can be observed densely at once.** Everything
downstream — token breadth (46 tokens), effective sample size (~30), and therefore the ability to
learn token selection at all — follows from that one number.

It is also a **user-decided budget item** (an increase was declined in round 79; partial increases
were approved in rounds 83 and 88), so it is not something to change silently. What this round
adds is the completed evidence base: every alternative explanation has now been eliminated by
measurement rather than assumed away.

## 4. What this round did NOT do

- Did not change the watch budget, the slot count, or any lease duration.
- Did not modify any production source.
- Did not promote, pause or retune any arm.
- Did not read the forward experiments as verdicts (`exit150_full15_v1` still at 17 settled).

## 5. Next actions

1. **P0 — read `exit150_full15_v1`** at 20 settled (17 now). Realised PnL per position; decompose
   any write-off claim into full-loss versus partial (round 27's standing rule).
2. **P0 — re-measure distinct-pool coverage** once ≥6 post-change 10-minute buckets exist
   (adaptive cadence, round 22), against the trend.
3. **P1 — slot TURNOVER as a no-budget lever.** With leases of 120 s / 300 s the 30 slots can
   admit at most ~360 dense pools/hour. Shortening effective lease duration, or admitting a
   replacement earlier once a pool has produced no signal, raises distinct pools per hour at
   unchanged request volume. `observation_leases145.replaceable_early` currently only evicts
   `bucket == "early"` leases, so growth/mature leases squat their full term — that asymmetry is
   the concrete place to look. Must be measured, not assumed: fewer frames per pool risks the
   ≥3-frame/30 s window that everything else depends on.
4. **P1 — the residual after the activity floor**: `bp`-low BSC positions still show 21.8%
   write-off (round 24).
5. **Do NOT** re-open: arm pruning (r25), token-level exclusion search (r26), quoting a write-off
   rate as a loss rate for partial-exit arms (r27).

## 6. Probe artifacts

`data/research/diag_round120/`, read-only: `r28_account_constraint.py`, `r28b_capacity.py`.
