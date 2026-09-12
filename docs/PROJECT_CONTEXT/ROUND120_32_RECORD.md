# ROUND 120-32 RECORD — provider reliability is not the bottleneck; and round 31's crash attribution was wrong

Date: 2026-09-13
Epoch: `chain-meme-trader/funding-20260906-v002-final-1000`
Mode: paper (`live.enabled=false`).
Change: `src/memetrader/cli.py` (one observability fix) + `tests/test_cli_crash_reporting.py`.

## 1. Provider reliability measured — it is not part of the bottleneck

The objective names "网络波动、数据异常" (network fluctuation, data anomalies) and this dimension had
not been measured. The mark tables carry `status`, `failure_kind`, `consecutive_misses`,
`first_missing_at`, `last_attempt_at` and `last_success_at`, so it is directly observable.

| check | result |
|---|---|
| mark history (19,590 rows) | **99.7% `VISIBLE`**, 0.3% `MISSING:NO_VISIBLE_POOL_OR_PRICE` |
| live per-pool marks (1,398) | **99.2% `VISIBLE`** |
| `consecutive_misses` | **1,397 of 1,398 pools have ZERO** |
| `last_success_at IS NULL` | **0 of 1,398** |
| staleness (`last_attempt_at` − `last_success_at`) | p50 / p90 / p99 all **0 s**; max 4,350 s (one pool) |
| providers | dexscreener 99.7% ok · geckoterminal 100% ok |

Failures are concentrated in a **single pool** (68 consecutive misses) out of 1,398. The only
other anomalies are 9 pools with `DATA_REJECTED:QUOTE_USD_UNKNOWN,quote_liquidity_unavailable` and
1 with `TimeoutError`.

**Conclusion: source reliability is not part of the coverage bottleneck.** Combined with round 29 —
where 95.6% of observed tokens never receive a third frame — the frames are not being *lost to
failures*; they are never *requested*. The observation gap is a budget/admission issue, not a
data-quality one, which keeps the remedy unchanged.

## 2. Round 31's crash attribution was WRONG, and this round corrects it

`cli._run_runtime` has two failure paths with **different exit codes**:

```python
except RuntimeError as exc:   # a REFUSAL TO START (single-instance lock)  -> return 3
except Exception:             # a real crash (e.g. httpx.InvalidURL)       -> return 1
```

Counting short runs (<5 s) by exit code in `paper-supervisor.log`:

| hour | exit=1 (crash) | exit=3 (refused start) |
|---|---|---|
| 23:00 | 4 | 0 |
| **00:00** | 5 | **377** |
| 01:00 | 0 | 3 |
| 02:00 | 0 | 3 |
| **04:00** | 0 | **64** |
| **total** | **10** | **447** |

**The dominant startup-failure mode is exit=3 — the single-instance lock refusing to start — at
447 runs versus 10 real crashes.** `runtime.py:817` raises
`RuntimeError("another memeTrader process is already running: …")`, and that path wrote **nothing**
to any log.

Round 31 attributed the 382-run and 64-run bursts to the `httpx.InvalidURL` crash. **That was
wrong.** The error was mistaking a coincident timestamp for causal attribution:
`runtime-crash.log`'s last write was 00:00:27, inside the 00:00 burst window — but that burst
contained **both** 5 httpx crashes (which wrote the log) and 377 lock refusals (which could not).
The exit code had already separated the two modes, and I did not use it.

What round 31 got right and still stands: the `httpx.InvalidURL: Invalid port: ':1]'` defect is
real, reproduced, isolated to the bracketed `[::1]` in `NO_PROXY`, and **already fixed** by
`trust_env=False` (commit `2064db9`). It is simply a *minor* mode — 10–20 events, not 446.

## 3. The fix shipped this round

Because the dominant mode (447 runs) left no evidence, the `RuntimeError` path now records its
traceback to the same `runtime-crash.log`, via a new `_record_runtime_crash(root, detail)` helper
shared by both paths. The exit code (3), the stderr line and every other behaviour are unchanged.

The helper never raises: logging must not become the reason a process fails to report its own
failure.

`tests/test_cli_crash_reporting.py` (6 tests) pins that a refused start records its **frame chain**
(a bare message is not diagnosable), that the log appends rather than truncates, and that a
logging failure is swallowed.

This names a concrete observed failure — 447 unlogged startup failures — as this project's rules
require of a defensive change.

## 4. What this round did NOT do

- Did not change any strategy, arm, threshold, exit contract or the observation budget.
- Did not touch the mark/collector path (§1 found nothing to fix there).
- Did not re-ship the `NO_PROXY` normaliser deleted in round 31 (still unnecessary).
- Did not read the forward experiments as verdicts (`exit150_full15_v1` at 18 settled).

## 5. Next actions

1. **P0 — read `exit150_full15_v1`** at 20 settled (**18 now**, +0.41U/pos, 83.3% win, 5.6%
   write-off). Two to go. Realised PnL per position; decompose any write-off claim into full-loss
   versus partial (round 27 rule).
2. **P0 — keep the experiments running.** They are the only source of new information and need
   wall-clock time.
3. **P1 — the 447 refused starts now have a cause recorded for the next occurrence.** The historical
   bursts are explained as "the lock was held"; *why* it was held (a stale lock from a killed
   process, or a genuine double start) cannot be recovered retroactively. If it recurs, the new log
   line will say so directly.
4. **P1 — the residual after the activity floor**: `bp`-low BSC positions still show 21.8%
   write-off (round 24).
5. **Do NOT** re-open: arm pruning (r25), token-level exclusion (r26), the capital hypothesis
   (r28), slot turnover (r29), the dense-episode-free lane (r30), the httpx `NO_PROXY` fix (r31),
   or provider reliability (r32 §1).

## 6. Probe artifacts

`data/research/diag_round120/`, read-only: `r32_provider_reliability.py`,
`r32b_crashlog_path.py`, `r32c_exit_codes.py`.
