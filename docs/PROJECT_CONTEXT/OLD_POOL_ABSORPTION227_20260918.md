# Stage 227: old-pool absorption breakout Paper arm

## Why this experiment exists

The current-period old-pool revival family is mostly loss-making. In the latest manual readback, `alpha149_live_flow_revival` had 256 terminal tokens, -983U net and 60 full writeoffs; `activity211` had 2/-5.32U and `activity193` had only 4/+2.68U. Those are account results, not matched causal comparisons. The user asked for a distinct implemented strategy, especially for old tokens that wake up again, without another data provider or future labels.

This arm tests a different entry hypothesis from a fast positive-flow trigger: observed sell pressure is absorbed while the exact pool's price and liquidity hold, followed by a later breakout. It cannot infer a true order book, wallet cluster or sellability from this pattern. Normal shared safety, exact-pool execution conditions, next-observed Paper BUY and cost model still apply. No historical cases are backfilled.

## Implemented contract

`activity227_old_pool_absorption_breakout_v1` is an isolated Paper arm. A first fresh same-pool DEX frame must show a pool age >=6h, liquidity >=max(2000U, current floor), at least 8 five-minute trades, >=500U five-minute volume and sells >=max(3, buys). A second independent observed frame 15-90s later must hold the first price and liquidity. A third independent frame another 15-90s later must still hold depth and be >=8% above the first price. The three frames must have the same chain, token, pool and provider; each must obey local observed <= ingested <= recorded <= decision and be <=30s old. Missing values refuse a signal, not become zero. The tracker is restart-local and bounded to 1024 token/pool states and fired keys. It uses existing shared frames and no extra API calls.

The arm clones `activity193`'s normal sizing, stop and execution contract, with a five-minute maximum hold and 20U ordinary Paper order size. It is append-only: existing arms, holdings, funding and histories are unchanged. The registered policy requests two simultaneous positions, but the existing effective-policy normalization makes the **actual runtime limit eight** for every arm. This discrepancy is visible in the focused test and must not be described as a two-position operating cap. A single arm can thus expose up to eight ordinary 20U entries before fees or exits.

## Verification and deployment

- `tests/test_old_pool_absorption227.py`: four tests passed. They cover three-frame triggering, no future or missing timestamp use, wrong pool/depth rejection, idempotent registration and actual effective concurrency eight.
- Earlier combined `test_activity_tempo193.py`, `test_activity_flow224.py` and the four new tests: 14 passed. The later narrow run after the cap assertion: four passed.
- Existing supervisor reloaded the Paper worker; `/health` returned running on the unchanged `chain-meme-trader/funding-20260906-v002-final-1000` period. Policy-addition row 384 activated at `2026-09-18T02:09:39.716521Z`, snapshot frontier 1268209. Frontier advanced past 1268261 at first readback. The arm had zero natural decisions and zero positions at that cutoff. It is **implemented and running, not yet naturally validated or profitable**.
- Pre-reload observer window (n=120) had p95 interval 2.65s, duration 1.06765s, failures 0. Early post-reload window (n=24) had p95 interval 4.3069s, duration 1.3027s, failures 0; passive queue 72 enqueued/70 processed/0 dropped. These are unequal-load windows, not proof of performance improvement or regression. A comparable-load readback remains necessary.

## Manual forward review and rollback

Do not schedule or auto-promote. At a user-triggered review, inspect independent terminal token count, net after buy/sell slippage and fees, sell failures, writeoffs, hold time, and overlap with ordinary old-pool controls. If 30 independent terminal tokens have net <=-150U or >=10 writeoffs, pause **new entries only** for investigation; this is a review trigger, not an automatic trading rule or proof of negative expectancy. If no signal appears, inspect frame cadence/feature availability before changing thresholds. Rollback is a reversible account-control entry pause for this arm; existing positions keep their recorded exit contract. The new module and runtime registration may be reverted only as a separately scoped code change, without deleting the policy row or historical trades.

No claim is made that historical user-selected hot tokens would have satisfied this signal at the time; their later outcome was not used as an input. The larger 12-section audit remains partial, especially matched ordinary/failed controls and load-matched shared-path performance.
