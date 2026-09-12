# ROUND 120-31 RECORD — the largest stability defect found, explained, and confirmed already fixed

Date: 2026-09-13
Epoch: `chain-meme-trader/funding-20260906-v002-final-1000`
Mode: paper (`live.enabled=false`). **Read-only round; no production code changed** (a candidate
fix was written, tested, and then deliberately removed — see §4).

## 1. Why stability, and what the log showed

Stability is one of the five dimensions the objective names and it had not been audited this
session. `data/logs/paper-supervisor.log` holds 483 run records:

| exit code | runs |
|---|---|
| **3** | **455** |
| 1 | 15 (my own restarts: `taskkill`) |
| −1 | 13 |

**457 of 483 runs lasted under 5 seconds** — startup failures, restarted every 5 s. They cluster in
two bursts:

| hour (local) | short runs |
|---|---|
| 23:00 | 4 |
| **00:00** | **382** |
| 01:00 | 3 |
| 02:00 | 3 |
| **04:00** (at 04:48) | **64** |

The most recent runs are healthy and long (463 s → 1,249 s), and the longest run on record is
2,672 s. So this is a **historical, recurring crash-loop mode**, not a current one.

## 2. Root cause, from the crash log

`data/logs/runtime-crash.log` (400 lines, last written 2026-09-13 00:00:27 — matching the 382-run
burst) contains 10 identical tracebacks ending in:

```
File ".../httpx/_urlparse.py", line 411, in normalize_port
    raise InvalidURL(f"Invalid port: {port!r}")
httpx.InvalidURL: Invalid port: ':1]'
```

via `httpx/_client.py:1412` → `collectors.py:1263` (`_new_client`) ← `collectors.py:1211` ←
`runtime.py:1485`.

httpx builds one `URLPattern` per `NO_PROXY` entry when constructing a client. **Any** construction
failure kills the process at startup, which the supervisor then restarts — a crash loop.

## 3. Reproduced and isolated

The live environment carries:

```
NO_PROXY = 'openreview.net,.openreview.net,api.openreview.net,api2.openreview.net,localhost,127.0.0.1,::1,[::1]'
HTTP_PROXY = HTTPS_PROXY = 'http://127.0.0.1:7890'
```

- **`httpx.AsyncClient()` with the live environment raises `InvalidURL: Invalid port: ':1]'`** —
  reproduced exactly.
- **Per-entry isolation: `NO_PROXY='[::1]'` ALONE raises.** Every other entry alone is fine, and
  the unbracketed `::1` is fine.
- So the sole culprit is the **bracketed IPv6 loopback `[::1]`**, which httpx reads as host `[`
  with port `:1]`.

## 4. It is already fixed, so no new code was shipped

The decisive test:

| client options | result with the malformed `NO_PROXY` |
|---|---|
| `trust_env=True` (httpx default) | **RAISES `InvalidURL: Invalid port: ':1]'`** |
| **`trust_env=False`** | **OK** |

**Every httpx client construction in the current code sets `trust_env=False`** — three in
`collectors.py` (one of them via `_client_options`) and one in `cli.py`; all verified in the
committed version at `HEAD`. `trust_env=False` was introduced by commit **`2064db9`** *"port the
runtime to a partially filtered host: explicit egress + sanitized launcher"* — exactly the change
that removes host-proxy inheritance.

I wrote a candidate fix (an in-process `NO_PROXY` normaliser that unbrackets bare IPv6 entries),
verified it against 8 cases including `[::1]:8080` and `None`, and confirmed it preserved the
bypass intent — **then deleted it**. The current code is immune, so the repair would have changed
nothing, and this project's rules are explicit that a defensive mechanism must name the observed
failure it changes. `src/memetrader/egress_env.py` was removed and no source file was modified.

## 5. A methodological note

Two of my own probes in this round were wrong before they were right, and both would have produced
a false conclusion if I had stopped at the first result:

1. the entry-isolation probe used `httpx.URLPattern`, which is not exported at the top level, so
   **every** entry looked unparseable and the "drop the bad ones" test silently cleared the whole
   `NO_PROXY` list instead of isolating one entry;
2. a regex scan for clients "lacking `trust_env`" captured only the first line of multi-line calls,
   so it reported two false positives (and one on my own scratch file).

The per-entry `AsyncClient()` test — the behaviour that actually matters — is what settled it.

## 6. What this round did NOT do

- Did not ship the candidate fix (§4 gives the reason).
- Did not modify the machine environment, the scheduled task, or `config.json`.
- Did not modify any production source; working tree verified clean for `src/`.
- Did not read the forward experiments as verdicts (`exit150_full15_v1` still at 17 settled).

## 7. Next actions

1. **P0 — read `exit150_full15_v1`** at 20 settled (17 now). Realised PnL per position; decompose
   any write-off claim into full-loss versus partial (round 27 rule).
2. **P0 — keep the experiments running.** They are the only source of new information and need
   wall-clock time.
3. **P1 — the 04:48 burst is not fully explained.** The crash log was last written at 00:00, so the
   64-run burst at 04:48 either took a different path or wrote elsewhere. Low priority now that the
   current code is immune, but worth a look if startup failures recur.
4. **Watch item:** the crash loops are environment-dependent — a malformed `NO_PROXY` in whatever
   launches the process. If startup failures recur, check that variable first.
5. **Do NOT** re-open: arm pruning (r25), token-level exclusion (r26), the capital hypothesis
   (r28), slot turnover (r29), the dense-episode-free lane (r30), or this fix (r31).

## 8. Probe artifacts

`data/research/diag_round120/`, read-only: `r31_stability.py`, `r31b_crash_trigger.py`,
`r31c_repro.py`, `r31d_isolate.py`, `r31e_fix_check.py`.
