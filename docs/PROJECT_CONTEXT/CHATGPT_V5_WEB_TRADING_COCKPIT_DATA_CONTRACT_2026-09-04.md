# V5 Web Trading Cockpit and Data Contract

Date: 2026-09-04
Status: `PRODUCT/OPERATIONS SPEC / PERSISTED-STATE READS ONLY`

## 1. Product goal

The Web system is an operating cockpit for a continuously running autonomous trading/learning system. It is not a research slide deck, a historical-stage gallery, or a browser-triggered market-data client.

At a glance it must answer:

1. Is each critical subsystem alive and producing current data?
2. Are new tokens/opportunities being discovered now?
3. Are any positions in danger or waiting to exit?
4. Is the execution queue keeping up?
5. What capital/equity is executable, indicative or unknown?
6. Which strategies have enough comparable evidence to rank?
7. What changed recently in strategy/data/execution versions?

Every Web request reads persisted/precomputed state. It must never issue Jupiter, RPC, DEX, Agent or broker activity.

## 2. Information hierarchy

### Home: `/cockpit`

Only the most operationally important facts:

- mode and Live lock;
- critical exit/dead/writeoff banner;
- subsystem pulse strip;
- discovery/decision/execution funnel;
- open-position risk board;
- executable portfolio truth;
- current execution queue and recent fills/failures;
- mature Top strategies or explicit `LEARNING / UNRANKED`;
- current active versions and recent controlled changes.

### `/strategies`

- all v5 independent strategy definitions;
- entry family, exit/treatment policy, activation frontier, Paper role and Live eligibility;
- account/position/outcome metrics;
- exact paired comparisons;
- maturity/promotion state;
- v4 appears only in History, not mixed into v5 ranks.

### `/positions`

- one row per virtual/physical position with clear distinction;
- risk state, remaining raw amount/cost, exact holding surface;
- fresh full-size executable recovery and age;
- latest flow/account/route warnings;
- pending ExitIntent/attempt and queue latency;
- strategy allocations.

### `/execution`

- OrderIntent -> Plan -> Attempt -> Fill/terminal timeline;
- queue/provider/total latency distributions;
- route legs, amount, min/central outputs and cost completeness;
- no-route, stale, protocol-invalid, error, ambiguous-send and reconciliation states;
- quote-capacity demand/utilization.

### `/tokens/:token_id`

- immutable identity and launch/surface lineage;
- discovery sources and times;
- current/decision-linked MarketFrames;
- exact pool/vault/mint events;
- all strategy decisions and allocation paths;
- post-buy investigation case/evidence;
- transaction/signature/explorer links when safe.

### `/risk`

- `DATA_STALE`, `MARKET_STALLED`, `PRICE_FLAT_WARNING`, `SELLABILITY_DEGRADED`, `EXACT_ACCOUNT_ALERT`, `DEAD_TERMINAL` and `WRITTEN_OFF` separated;
- exact reason/source/availability time;
- alerts that did and did not lead to economic exits;
- permanent no-reentry surfaces.

### `/learning`

- full opportunity shadow versus capital-feasible Paper;
- gate-ablation cohorts;
- paired exit contrasts;
- cluster/date/regime robustness;
- open/right-censored outcomes;
- promotion/stop lifecycle;
- Agent-treatment coverage and latency.

### `/chains`

- Solana, BSC, Robinhood separately;
- discovery, route, simulation, cost, safety, Paper and Live maturity;
- chain-specific blockers;
- Robinhood RWA/stock exclusion status.

### `/system`

- runtime/DB/WAL/process/task;
- collectors/subscriptions/provider health;
- queues, oldest due, p50/p95 latency, gap/error rates;
- storage/write/query latency;
- Agent state/budget when enabled;
- current read-only public/local control scope.

### `/history`

- immutable v1–v4 evolution, supersessions and prior results;
- never shown as current independent-strategy alpha.

## 3. Cockpit API contract

Recommended bounded endpoint:

`GET /api/v5/cockpit`

Response:

```json
{
  "schema_version": "v5-cockpit/1",
  "as_of": "UTC timestamp",
  "mode": {
    "execution": "paper",
    "live_enabled": false,
    "live_lock_reason": "...",
    "active_strategy_epoch": "..."
  },
  "pulses": [],
  "critical": {},
  "discovery": {},
  "funnel": {},
  "positions": {},
  "execution": {},
  "equity": {},
  "strategy_leaders": [],
  "versions": [],
  "recent_activity": [],
  "data_contract_warnings": []
}
```

The endpoint reads materialized/bounded views. It does not run deep all-history aggregation on each 1–2 second refresh.

## 4. Real subsystem pulses

Each pulse is driven by persisted work, not decorative animation:

```json
{
  "id": "token_discovery",
  "state": "healthy|quiet|degraded|stale|disabled|unknown",
  "last_attempt_at": "...",
  "last_success_at": "...",
  "last_item_at": "...",
  "age_seconds": 1.2,
  "expected_interval_seconds": 5,
  "items_1m": 48,
  "errors_15m": 0,
  "gap_count_15m": 0,
  "latest_sequence": 123,
  "reason": ""
}
```

Required pulses:

- Runtime scheduler;
- SQLite writer/WAL;
- Pump/PumpSwap discovery;
- Token hydration;
- PumpSwap logs/account stream;
- held-account subscriptions;
- MarketFrame generation;
- Jupiter quote scheduler;
- exit execution lane;
- Paper fill/position projector;
- passive information ingestion;
- post-buy Agent research when enabled;
- Web/API snapshot producer.

UI animation rules:

- pulse only when `latest_sequence` changes;
- quiet market and stale collector are different states;
- process/listener alive without recent scheduled work is not automatically healthy;
- `disabled` is neutral, not red;
- stale values are not shown as zero.

## 5. Critical banner

`critical` includes:

```json
{
  "pending_exact_account_exits": 0,
  "oldest_critical_exit_age_seconds": null,
  "exit_armed": 0,
  "dead_terminal_unsettled": 0,
  "execution_lane_blocked": false,
  "data_stale_open_positions": 0,
  "new_entries_paused": false,
  "pause_reason": ""
}
```

Priority display:

1. unresolved exact-account emergency;
2. exit queue blocked/late;
3. dead terminal awaiting settlement/writeoff;
4. open position with stale execution truth;
5. entry pause due capacity/operations.

A critical banner links directly to `/positions` or `/execution` with the exact filtered records.

## 6. Discovery and funnel

Display rolling windows and immutable epoch totals separately:

- raw discovery exposures;
- distinct tokens;
- first local discoveries;
- frame-ready candidates;
- each entry-family cohort;
- execution preflights;
- executable Paper opportunities;
- portfolio selected;
- BUY fills;
- open positions;
- exit intents;
- SELL fills/writeoffs.

The funnel is a DAG. Do not force unrelated information and token paths into one fake conversion percentage. Every count exposes its unit and denominator.

Token discovery pulse is based on newly persisted discovery/exposure sequence. It must continue to show activity even when no strategy admits a trade, so the user can distinguish “market quiet” from “strategy/pipeline blocked”.

## 7. Open-position risk board

Each row/card includes:

- Token/symbol/short address and deep link;
- chain/surface/pool;
- strategy and virtual/physical allocation;
- opened time/age;
- remaining raw amount and cost;
- risk state and state-since time;
- fresh executable full-size recovery, ratio and quote age;
- central indicative recovery separately;
- current recovery high-water/drawdown;
- latest flow/breadth/intensity summary;
- exact vault/account alert status;
- pending exit action/attempt/latency;
- source/data quality flags.

Sorting defaults:

1. exact account alert/dead;
2. exit armed/quoting;
3. stale execution truth;
4. largest worst-case remaining loss;
5. oldest normal position.

Do not sort primarily by attractive percentage gain.

## 8. Equity truth

For each account/portfolio expose:

- cash;
- realized PNL;
- fresh conservative executable value of open positions;
- conservative executable unrealized/total PNL only when valuation coverage is complete;
- central quote estimate separately;
- indicative DEX mark separately;
- unknown/unpriced count and cost;
- worst-case remaining cost;
- valuation status and oldest quote age.

Labels:

- `CONSERVATIVE EXECUTABLE QUOTE BOUND`;
- `CENTRAL QUOTE ESTIMATE`;
- `INDICATIVE NON-EXECUTABLE MARK`;
- `UNKNOWN`;
- `LIVE RECONCILED` (unavailable while locked).

Null remains null. No route is a state, not a display zero, unless a terminal writeoff has been recorded.

## 9. Strategy ranking rules

A strategy can appear in Top ranking only when:

- it is a current v5 independent policy;
- it has reached the registered minimum maturity for ranking;
- its compared account valuation/outcome set is sufficiently complete;
- the displayed metric version is frozen;
- paired ranks use the exact comparable cohort set;
- top-winner dependence is shown.

Before that, display:

`LEARNING · UNRANKED · N terminal / D dates / C independent clusters`

A strategy ranking card contains:

- conservative terminal PNL;
- median/trimmed mean;
- drawdown/expected shortfall;
- writeoff/no-route;
- capital-time efficiency;
- remove-best-1 result;
- maturity state;
- open/censored count.

The home page shows at most three mature leaders. `/strategies` shows all policies, including stopped/failed ones.

## 10. Recent execution activity

One normalized event stream:

- StrategyDecision;
- OrderIntent;
- plan/quote requested/completed;
- no-route/error/stale;
- Paper fill;
- risk-state change;
- ExitIntent;
- partial/full SELL;
- writeoff;
- post-buy research completed/expired;
- strategy version activated/stopped/promoted.

Each event exposes only allowlisted data and links to its lineage. It identifies `PAPER`, `SHADOW`, `RESEARCH`, or future `LIVE` prominently.

## 11. Version and learning state

Show current versions for:

- strategy epoch;
- entry family;
- exit policy;
- MarketFrame/decoder;
- execution/cost adapter;
- held-account monitor/rug terminal;
- post-buy research/treatment;
- Web schema.

A version card includes activation frontier/time, status, changed fields and prior version. No UI control edits an immutable strategy definition in place.

## 12. Local operational controls

Public/remote console remains read-only. Local authenticated loopback may expose append-only operational commands only after backend authorization:

- pause/resume **new entries**;
- pause optional research/Agent work;
- request Paper emergency flatten;
- acknowledge an operational alert;
- rotate display/filter preferences.

Rules:

- pausing entries never pauses exits/held-account monitoring;
- commands create immutable command/audit rows;
- a strategy parameter change creates a new registered version, not a mutable setting;
- no Web action enables Live;
- no secret/private key/transaction payload is returned.

Future Live emergency flatten requires a separately reviewed command/signing path and cannot be silently inherited from Paper UI.

## 13. Incremental update mechanism

The existing 2-second persisted-state polling is acceptable initially if queries are bounded. Recommended enhancement:

- `/api/v5/cockpit` for snapshot;
- `/api/v5/activity?after_id=<cursor>&limit=<bounded>` for changes;
- optional Server-Sent Events driven from persisted activity sequence, never provider calls.

The browser stores the last cursor, detects sequence gaps and requests a fresh snapshot. It never invents missing events.

## 14. Backend materialized snapshot

A runtime/store process updates compact current projections after relevant commits:

- per-strategy account snapshot;
- open-position risk projection;
- queue/capacity summary;
- subsystem heartbeat summary;
- funnel rolling counts;
- maturity/rank summary.

The Web server performs read-only SQLite queries with short timeouts. Expensive all-history learning views run on bounded cached reports or explicit secondary-page requests, not the cockpit loop.

## 15. Responsive visual structure

Desktop above the fold:

1. mode/version/clock and Live lock;
2. critical banner;
3. pulse strip;
4. executable equity + open risk + exit queue;
5. discovery/funnel + recent execution;
6. mature Top 3 or learning state.

Mobile:

- critical/risk and exit queue first;
- pulse strip horizontally scrollable;
- compact position cards;
- research/history collapsed by default.

Color is redundant with text/icon/state. Motion respects reduced-motion preference and never substitutes for a timestamp.

## 16. Data-contract warnings

The API returns explicit warnings such as:

- incomplete executable valuation;
- stale subscription/quote;
- cost incomplete;
- insufficient maturity;
- unmatched cohort comparison;
- current strategy epoch not yet active;
- public read-only mode;
- Live locked.

The UI does not hide them to look cleaner.

## 17. Performance/operability objectives

Measure rather than assume:

- cockpit snapshot query latency p50/p95;
- response size;
- browser render time;
- SQLite writer contention caused by projections;
- sequence gaps/stale UI;
- oldest operational state shown.

Initial targets can be registered after measuring the current system. Do not solve a slow page by increasing timeout indefinitely or issuing provider calls from the browser.

## 18. Acceptance tests

- discovery animation changes only after a persisted discovery sequence advances;
- quiet and stale states render differently;
- an exact-account alert appears ahead of ordinary cards and links to lineage;
- unknown equity never renders `$0` or a fabricated rank;
- v4 appears in History, not v5 leaderboard;
- immature v5 policies show `UNRANKED`;
- same shared fill appears once in execution and under each virtual allocation without multiplying gross physical capital;
- public endpoint cannot issue commands;
- local pause-new-entries leaves exits running;
- no cockpit/API request causes Jupiter/RPC/Agent/broker work;
- bounded query/render remains usable as historical tables grow.
