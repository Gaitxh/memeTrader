# ROUND 120-33 RECORD — the refused-start fix verified end-to-end, and the 447-run mode explained

Date: 2026-09-13
Epoch: `chain-meme-trader/funding-20260906-v002-final-1000`
Mode: paper (`live.enabled=false`). **Read-only round; no production code changed.**

## 1. Why this round verified rather than explored

Round 32 shipped a change to `cli.py` (the refused-start path now records its traceback) but the
running trader predates it, so nothing had exercised the new code. Every diagnostic line is now
closed by measurement — capital/concurrency (r28), slot turnover (r29), the dense-episode-free
lane (r30), the httpx `NO_PROXY` defect (r31), provider reliability (r32) — so the highest-value
action was to **confirm the one change I had shipped actually works**, rather than open another
line.

## 2. The verification, done safely in production

The single-instance lock means a second trader correctly refuses to start, so attempting one is a
**zero-risk** way to exercise the exact path that was fixed — the second process cannot write to
the database because it never gets past the lock.

| step | result |
|---|---|
| lock file | `data/memetrader.lock`, present, 1 byte |
| crash log before | 22,020 bytes |
| second `memetrader run` instance | **exit code 3**, message `another memeTrader process is already running: …\data\memetrader.lock` |
| crash log after | **22,904 bytes** |

The new entry, verbatim in structure:

```
RuntimeError (refused start): another memeTrader process is already running: …\data\memetrader.lock
Traceback (most recent call last):
  File "…/runtime.py", line 810, in __enter__
    msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
PermissionError: [Errno 13] Permission denied

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "…/cli.py", line 123, in _run_runtime
    with SingleInstance(lock_path):
  File "…/runtime.py", line 817, in __enter__
    raise RuntimeError(f"another memeTrader process is already running: {self.path}") from exc
RuntimeError: another memeTrader process is already running: …
```

**The fix works**: the refused start is now recorded with its **full frame chain**, including the
chained cause. A bare message would not have been diagnosable; the chain is what identifies the
mechanism.

## 3. The 447-run mode is now explained, not just counted

The recorded chain names the underlying mechanism directly:

**`msvcrt.locking(handle, msvcrt.LK_NBLCK, 1)` raises `PermissionError: [Errno 13]`** when another
process holds the byte range, and `SingleInstance.__enter__` converts that into the `RuntimeError`.

So the 447 short `exit=3` runs across two bursts were **the lock being held at startup** — a stale
holder or a genuine overlapping start — and each restart failed within ~0.5 s exactly as observed.
Round 31 could not see this because the path logged nothing; round 32 made it visible; this round
confirmed the visibility works and read the mechanism off it.

**Residual limit, stated honestly:** *why* the lock was held in those two windows cannot be
recovered retroactively. Windows byte-range locks are released when the holding handle closes, so a
merely-killed process should not hold it — which points at either an overlapping start or a process
that was alive but not the trader. The next occurrence will be directly diagnosable from the log.

## 4. Deployment note

The verification exercised the **current** `cli.py` via a directly-invoked instance. The live
trader process started at 06:01 and therefore still carries the pre-r32 `cli.py`; the change takes
effect on its next restart. No restart was performed for this — it is not needed, and a restart
would clear the running process's in-memory observation state for no benefit.

## 5. What this round did NOT do

- Did not modify any production source; staged nothing under `src/`.
- Did not restart the trader, change the observation budget, or touch any arm.
- Did not leave the system in a degraded state: the test instance was refused before it could
  reach the database, and the sole side effect is one honest log entry recording a real event.
- Did not read the forward experiments as verdicts (`exit150_full15_v1` at 18 settled).

## 6. Next actions

1. **P0 — read `exit150_full15_v1`** at 20 settled (**18 now**, +0.41U/pos, 83.3% win, 5.6%
   write-off). Two to go. Realised PnL per position; decompose any write-off claim into full-loss
   versus partial (round 27 rule).
2. **P0 — keep the experiments running.** They are the only source of new information and need
   wall-clock time; do not manufacture work to fill the gap.
3. **P1 — the residual after the activity floor**: `bp`-low BSC positions still show 21.8%
   write-off (round 24). Note the effective sample is ~19 BSC tokens, so any rule discovered there
   needs the round-26 permutation treatment before it is believed.
4. **Watch item:** if startup failures recur, `runtime-crash.log` now records
   `RuntimeError (refused start)` with the chain — read it first.
5. **Do NOT** re-open: arm pruning (r25), token-level exclusion (r26), the capital hypothesis
   (r28), slot turnover (r29), the dense-episode-free lane (r30), the httpx `NO_PROXY` defect
   (r31), provider reliability (r32), or this fix (r33 — now verified).

## 7. Probe artifacts

No new probe scripts; the verification used the live system and `data/logs/runtime-crash.log`.
