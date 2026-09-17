# Manual Paper strategy decision, 2026-09-17

## Scope and cutoff

Current definition is `chain-meme-trader/funding-20260906-v002-final-1000`; Paper remains running and Live locked. The pre-change read used current SQLite closed/written-off positions at about 01:09 UTC, not retrospective hot-list prices. Accounts use 20U notional and configured 4% adverse slippage on each side, 0U extra fee and a 1000U original-pool floor. Counts below are independent token positions per named arm; overlapping arms are correlated, not independent evidence.

## Diagnosis and strategy decisions

`migration209_first_tradable_v1` had 37 terminal tokens, net -191.2451U; 20 hard-stop exits lost -211.23U in aggregate. `migration214_pool_persistence_v1` had 30 terminal tokens, net -95.8697U; 14 hard-stop exits lost about -143.26U at the earlier 01:05 read. Among 23 shared closed tokens, the 214-minus-209 net sum was only about +1.17U, and only five shared exactly the same source BUY, all tied. The second frame was not a demonstrated economic improvement. The exact losses vary as new trades settle, so the timestamped terminal totals above are the convergence decision boundary.

Manual convergence `scripts/converge_migration219.py --apply` wrote only the existing account-control KV overlay at `2026-09-17T01:09:33.492338Z`, receipt `migration219:convergence:2026-09-17T01:09:33.492338Z`. Both arms now have `FAILED_FORWARD_EXPECTANCY` and `entry_paused=true`. No existing policy, position, fill or account history was deleted or refunded; the one formerly open 214 position had naturally closed before the pause. The old rules and receipts remain available for audit. Rollback is a deliberate restoration of the receipt's `previous_control` for these two keys, not a reset of the funding period.

The alternative washout-reclaim structural exit remains worth observing: `alpha212_washout_reclaim_anchor_v1` has six closed positions and -4.3944U net. Four fully terminal same-source-BUY pairs against its slow-hold control all favored 212 by a combined +50.33957U; a fifth control position was still open at the pair read and is excluded from this terminal claim. This is not proof of positive expectancy.

## New distinct test: trend-anchor220

`trajectory220_breakout_anchor_v1` copies the existing `trajectory144_trend_runner_v1` frozen early-activity entry and runner exit. At the signal's actual 30-90 second, three-point original-pool feature window, it freezes the window's starting price as `current_price / (1 + observed_return)` with the window start timestamp. If, after the source BUY, two distinct fresh marks from that same original pool fall below the frozen breakout origin within 60 seconds, the existing next-observed SELL path is requested. Recovery or a gap resets the two-mark streak. Existing hard stop, trailing, maximum hold, original-pool loss and Paper costs still apply. This is an exit-mechanism test, not a replay fitted to user-selected winners. It uses no new API and no later high/price as an entry feature. Missing or future window clocks reject only this arm's signal.

Source: `src/memetrader/trend_anchor220.py`; routing/registration and generalized frozen-anchor persistence: `runtime.py`, `store.py`. Focused `test_trend_anchor220.py` plus `test_washout_reclaim212.py`: 8 passed. Paper supervisor restarted its exact old worker, then loaded new worker PID 112480. The new strategy registered at `2026-09-17T01:14:05.770435Z`, snapshot 1021134, with 508 current policies; 209/214 remain paused, existing period unchanged, HTTP `/health` running. There were zero natural 220 positions at deployment. No claim of profitability or measured runtime improvement is made.

## Open work and next manual read

Compare 220 and its source runner only for shared source BUY and fully terminal independent tokens: net difference, failed-exit/writeoff frequency, right-tail capture and latency. Check whether the pre-impulse anchor is too far below entry to avoid losses or triggers on recoverable volatility. A new arm must not tax shared collection; runtime frame processing is one O(1) alias per existing signal and no external request. Recheck hot-path timing and held quote ages under comparable load. The full user-sample case/control reconstruction, 508-policy family dispositions, discovery-clock gaps and costed long-run effectiveness remain partial, as recorded in `memory/ACTIVE_EXECUTION_SCOPE_20260917.md`.
