# SERVICE-DOWN145 recovery — 2026-09-10T17:32Z

ACK `C2C-20260911-145-SERVICE-DOWN`. Root Codex remains the sole writer. Root was not deploying when the incident was reported; Chat reported no process mutation. Lower-priority implementation was not started before recovery.

## Incident and action

Fresh read confirmed no project Paper/Web process or 8790 listener. The previous manifest still named PID30748/15:53:23Z. The supervisor log had no new exit/restart record after10:41Z; runtime-crash.log remained Sep2 UTC. Last old runtime stdout at17:07Z was a provider ReadTimeout, without a terminating traceback. Bounded Application1000/1001 and System1074/6006/6008 reads for17:20–17:28Z returned no records. This does not establish why both service processes disappeared; no intentional root deployment stop or current Python crash is proven.

The current user request was executed through existing `scripts/start_system.ps1 -NoOpen -WaitSeconds 60`, which invoked existing `run_paper.ps1` and `open_chain_web.ps1`. This attempt was allowed; no alternate control surface, new scheduler, reset or policy change was used. No existing process was killed, and no second Paper service was launched.

The wrapper initially exited1 because its `/api/live` first response exceeded15s. Processes remained running. Subsequent independent checks succeeded: health0.113s, live3.760s, performance0.201s. Thus recovery is established by real service evidence, not wrapper exit status. The cold-start readiness timeout remains a launcher diagnostic issue, not evidence that Paper failed to start.

## Loaded and healthy

- Paper supervisor43028 → venv17684 → Python30808; runtime manifest17:28:05.347873Z.
- Web wrapper27712 → venv5908 → Python20112; local8790 listening.
- All ten manifest source hashes match disk, specifically `runtime.py` and `mode_learning144.py` from committed/pushed `ae53fac`; no uncommitted trading source was loaded.
- At17:32:13Z API heartbeat age0.852s; Paper-only/Live locked. Same `chain-meme-trader/funding-20260906-v002-final-1000` period, ordinary400bps buy/sell costs and1000U floor.
- Three open positions/two held tokens, pending exit quotes0. RH/SOL original-pool mark ages4.993/5.262s, no current missing/failure/coverage gap.
- Stable recent120 held samples: fetchp95=2.444s versus first50 cold samples3.761s; applyp95=60.7ms. Passive computep95=1.139s (110 samples), queue waitp95=2.312s, enqueued479/processed472, drops0. Dex PoolTimeout0/connect_errors0/retired clients0. Cumulative held fetch failures2 means this is not a zero-error or long-run guarantee.

Bounded immutable readback matches144-before canonical JSON SHA256 for old25 registrations, old311 policy rows, one funding activation and zero funding restorations. First comparison used Unicode serialization instead of baseline ASCII escaping and therefore mismatched the two Chinese-containing tables; corrected baseline serialization matches exactly. No history rewrite or refund occurred.

## ae53fac natural callback boundary

First read:434 passive frames,4 passive labels. By17:32Z:3111 passive frames,1397 matched-episode advances,8 passive labels and2 new passive strict entries; Store callback also recorded1113 frames and3 entries. Counts are callback/episode events, not independent token profit samples. This proves the newly loaded path naturally executes; it does not attribute all old UNKNOWN labels to the old callback gap or demonstrate improved return. No old label was backfilled. Model remains the saved finite-mode learner; broad144 coverage/trend/strategy-generation acceptance stays open.

Evidence: `data/research/strategy_delivery144/service145_recovery.json` and `service145_stable.json`. Existing28 targeted tests of ae53fac already passed; no duplicate test run. New145 full implementation/UI/search contract is separate from this resolved service incident and has not been claimed delivered.
