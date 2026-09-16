# Old-pool activity interval validity, 2026-09-17

## Observed defect and scope

`activity193_old_pool_tempo_v1` estimates preceding-55-minute trade tempo from the same-frame Dex/Gecko `h1` and `m5` buy/sell counts. It previously subtracted only aggregate counts. A reproduced input with `m5 buys/sells=24/8` and `h1 buys/sells=20/44` emitted an 11x tempo signal even though the claimed hour contains fewer buys than its last five minutes. `activity200_old_pool_tempo_fast5_v1` aliases this signal, so the input defect reached both arms. No natural frequency or PnL attribution has been established.

The input check now requires `h1 buys >= m5 buys` and `h1 sells >= m5 sells` before computing the prior-55-minute baseline. Invalid frames produce no signal and do not mark the token/pool as already emitted. This changes only prospective signal validity in the shared observer; it does not change either registered policy, thresholds, 20U trade size, exits, existing positions, safety checks, original-pool floor, next-observation fills, API use or funding. Historic decisions remain unchanged; compare outcomes by the process activation boundary, not as one homogeneous policy sample.

## Engineering and runtime evidence

- `tests/test_activity_tempo193.py` now covers each contradictory side while aggregate totals could pass, equality boundaries, and a valid subsequent frame. Focused 193/200 tests: 7 passed.
- Before restart, the runtime source manifest matched every listed trading source file on disk except this edited `activity_tempo193.py`. Paper PID 96040, same funding version, Live locked, 1000U shared floor and 400/400 bps adverse buy/sell slippage. Snapshot frontier 971344; total historical position rows 38800.
- The existing `run_paper.ps1` supervisor restarted only its verified Paper child. New runtime PID 88208 started 2026-09-16 17:49:04Z and reports the exact edited source SHA-256. `/health`, `/api/live`, `/api/performance` succeeded; Paper=true, Live locked, same funding version. At 17:49:37Z heartbeat had advanced to 17:49:36Z, snapshot frontier to 971498, and position row count remained 38800. The one held Solana token had a 5.64-second quote age at that read, not a matched-load latency improvement claim.

This is a strategy input-validity correction, not a new alpha arm or a profitable result. The two natural arm outcomes remain sparse: 193 has one historical position, 200 has no filled position at this boundary. Retain their separate 30-minute/5-minute exit comparison, but do not attribute old trades to this fix or relax risk gates to force new fills. Next manual readback should count new valid/invalid tempo inputs and natural matched 193/200 opportunities; no scheduled research job was enabled.
