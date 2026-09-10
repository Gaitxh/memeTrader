# RESULT142 — held valuation and freshness display

User request: resolve positions shown as “持仓行情待更新”. Source and Web deployment completed; native reserve availability is a separate remaining constraint.

## Findings and change

- At 11:48Z, ordinary BSC held marks were about 2 seconds old. They were not a discovery/held-fetch outage. The full strategy response discarded mark provenance/time/sellability, and the UI did not recognize one valid configured Paper valuation source.
- Native Pump cohort94747 had a fresh `LOCAL_NO_DIRECT_CAPACITY` receipt, `native_capacity_budget_exhausted`. Its account was UNKNOWN, but generic position/token projections incorrectly substituted a fresh ordinary Dex valuation. It now consistently uses the native remaining-raw exit surface across overview, strategy and token detail. Missing native value stays null; it is neither zero nor an executable Dex fill. Partial-position unrealized value uses remaining allocated cost.
- UI now distinguishes native capacity insufficient, expired quote, fee evidence missing and migration pending, with the latest check time. Ordinary marks retain their current price/source/freshness. Native freshness ages use the native receipt, not token-level Dex time.
- A captured live response also proved a heartbeat read race: generated11:58:46.409669Z, heartbeat11:58:46.413208Z, incorrectly “stale/no heartbeat”. The compact clock is now taken after the first SQLite snapshot read; full/health heartbeat age is measured after reading the heartbeat. Actual future timestamps remain invalid.

## Validation and deployment

- Closest Python tests: native current/capacity/stale projections (3), existing ordinary missing/fresh/stale valuation cases (5), heartbeat read race and genuinely future timestamps (4): 12 distinct cases PASS. Native projection test was rerun only after adding native age assertions. Existing JS strategy revision test plus the new status-label assertions PASS; diff check PASS.
- Source commits f0317c3 and e32beb0 were pushed. Only the supported Web launcher was restarted; Paper PID40216 remained running throughout. No strategy, provider frequency, cash ledger, trade, funding or Live configuration changes.
- Actual existing browser was refreshed and showed “原生曲线可卖储备不足（1仓）”, alongside numeric ordinary account valuations and a current heartbeat.
- 12:04:22Z API readback: `/health` and `/api/live` running, Paper=true, Live locked, current funding `chain-meme-trader/funding-20260906-v002-final-1000`. 10 positions: 9 ordinary valued, one native UNKNOWN. Native check12:04:19.949387Z, remaining raw1284729855258; it continues through the existing held exit loop.
- Rolling telemetry at 11:48→12:04: held_fetch p95 2.035→2.670s; held_apply p95 33.8→55.0ms; passive wait p95 2.009→2.545s, drops0; Dex PoolTimeout0 and ConnectError3 unchanged. These are different natural load windows, not a controlled speedup claim. No new network work was introduced.

Evidence: `data/research/held_refresh142/before.json`, `after.json`, `final.json`. These are observation snapshots, not rewritten historical fills.

## Remaining boundary

94747 already had a partial native Paper exit in stage140; its remaining verified capacity is still insufficient. This UI/data projection fix cannot replenish onchain reserves or reset the persistent consumed-capacity budget. The system must wait for genuine new capacity or a verified migration surface; it must not fabricate a SELL, treat unknown as zero, or substitute another pool. Broader141 strategy work remains as recorded; no reopening of old implementation stages.
