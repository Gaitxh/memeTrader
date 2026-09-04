# V5 Storage, Latency and Runtime Architecture Specification

Date: 2026-09-04
Status: `ENGINEERING DESIGN / SINGLE PROCESS + SQLITE PRESERVED UNTIL MEASURED OTHERWISE`

## 1. Objective

Support fast held-position decisions, strict forward audit, long-term learning and a responsive Web console without multiplying provider work or turning SQLite into a full-chain tick warehouse.

Preserve the project’s preferred architecture:

- one Python Runtime process;
- one SQLite writer in WAL mode;
- bounded asynchronous collectors;
- read-only Web processes/connections;
- all project data under `E:\memeTrader`;
- no new distributed system unless a measured bottleneck requires it.

## 2. Three data temperatures

### Hot in-memory state

For active candidate/held pools only:

- 1s/3s/5s/15s/60s ring buffers;
- latest exact account/vault state;
- latest current executable quote facts;
- incremental flow/breadth/intensity aggregates;
- risk state and scheduler priority;
- dedupe sets for recent signatures/events.

This is reconstructable/ephemeral. It must never be the only record of a decision/fill/terminal event.

### Durable operational SQLite

Persist:

- registrations/frontiers/version hashes;
- candidate/cohort census and decisions;
- decision-linked/fixed-checkpoint MarketFrames;
- account/risk state changes;
- OrderIntent/Plan/Attempt/Fill/PositionEvent;
- no-route/error/missing/late/writeoff terminals;
- current projections/materialized snapshots;
- source event/signature/slot references;
- Agent cases/results and selection propensity.

### Optional cold raw archive

Only if measured raw stream volume/diagnostic needs justify it:

- append-only compressed transaction/event records under `E:\memeTrader\data\...`;
- daily bounded files/manifests/checksums;
- immutable archive pointer referenced by SQLite;
- never required for the live hot path.

Do not introduce Parquet/object storage merely for architectural appearance. Use it only after recording SQLite write/storage pressure or a research need for raw replay.

## 3. Market event retention

Do not persist the global PumpSwap firehose indefinitely.

For each decoded event:

- if it touches an active candidate/open position, keep ring-buffer state and a bounded raw operational row/reference;
- persist full normalized event when it causes a frame/risk/decision or is needed to explain a gap/decoder error;
- otherwise retain only aggregate counters/source health or optional cold archive.

At every decision/exit/checkpoint, freeze the full feature components and source lineage required to reproduce the decision. A later raw-event retention policy cannot erase decision evidence.

## 4. Suggested core schema groups

### Authority

- strategy epochs/definitions;
- entry frontiers/supersessions;
- decoder/MarketFrame/execution/cost/Agent treatment registrations.

### Shared market evidence

- market stream attempts/gaps;
- normalized decision-relevant pool events;
- immutable MarketFrames;
- exact account/risk events;
- route/surface observations.

### Strategy/portfolio

- cohorts/opportunities;
- decisions;
- selection/propensity/allocations;
- order intents.

### Execution

- plans;
- attempts;
- fills;
- position events;
- retry/deadline terminals.

### Projections/Web

- current position projection;
- account snapshots;
- queue/capacity summary;
- runtime pulses;
- bounded recent activity sequence;
- maturity/rank snapshots.

Definitions/frames/intents/plans/attempts/fills/events are append-only. Projections may update because they are reconstructable.

## 5. SQLite transaction discipline

- no network/RPC/Jupiter/Agent await while a DB transaction/lock is held;
- write attempt/intent in a short transaction, release, do side effect, append result in another short transaction;
- group tightly related local rows atomically where needed (e.g. v5 registry + v4 stop frontier);
- use explicit unique keys and `INSERT OR IGNORE`/compare-and-swap only where semantics are defined;
- keep payloads normalized/bounded; large raw responses remain internal references, not duplicated across strategies;
- configure/read current busy timeout/WAL checkpoint behavior based on measurement;
- Web uses read-only bounded queries and never holds long transactions.

## 6. Index plan

Create only indexes justified by hot queries. Candidate keys:

- `(definition_version, cohort_id, available_at)`;
- `(token_id, market_surface_id, available_at)`;
- `(pool_address, slot, event_index)`;
- `(intent_state, urgency, deadline_at)`;
- `(position_state, risk_priority, next_evaluation_at)`;
- `(attempt_state, requested_at)`;
- `(strategy_id, terminal_at)`;
- `(activity_sequence)`;
- `(pulse_id, recorded_at)`.

Use partial indexes for due/open/pending states when supported and measured useful. Do not add dozens of overlapping indexes to every append-heavy table.

## 7. Runtime task architecture

One Runtime owns:

- collectors/subscriptions;
- decoder/ring buffers;
- strategy/portfolio evaluation;
- execution scheduler;
- Paper adapter;
- position/risk projection;
- compact snapshot/heartbeat production.

Separate async queues by semantic priority but dispatch through one global capacity controller. Network clients can remain specialized; priorities/deadlines are centralized.

Long semantic Agent work runs in bounded subprocesses outside DB transactions. Results return through immutable case/result records.

## 8. Exit fast path

Held-account/log callbacks do minimal work:

1. validate/dedupe event;
2. update in-memory state;
3. append material exact event/risk transition;
4. enqueue/reprioritize position evaluation;
5. return.

Policy evaluation creates an immutable ExitIntent quickly. Jupiter/provider request occurs in the global scheduler. Heavy Web/report/Agent work never runs on the callback path.

## 9. Candidate path

Discovery/hydration can be high volume. Use staged bounded work:

- append discovery exposure;
- prioritize fresh Solana/Pump migration candidates;
- deterministic cheap feature/identity screen;
- create shared candidate/census;
- only candidates selected by family/risk-bucket scheduler request expensive route/preflight;
- one response feeds simultaneous eligible strategies.

Old bulk hydration/research cannot sit ahead of held exits or current launch deadlines.

## 10. Materialized current projections

Avoid reconstructing every account/position from full history on each Web poll. After relevant immutable events:

- update one current position projection row;
- update per-strategy account snapshot when economic state changes or at bounded interval;
- update queue/health/funnel counters;
- append a compact activity item.

Projection rows store source last-event IDs/hashes. A validator can rebuild/compare them without changing immutable history.

## 11. Web read isolation

- read-only URI/connection where possible;
- bounded limits/cursors;
- no `COUNT(*)`/joins over the full growing history in the 1–2 second endpoint;
- secondary learning pages use precomputed snapshots or explicit bounded queries;
- return `data_contract_warning` on query timeout/stale snapshot rather than displaying old values as current;
- measure query p50/p95 and response size.

## 12. Data freshness and clocks

Store distinct times:

- source/chain observed;
- provider received;
- local ingested;
- durable recorded/available;
- scheduler queued/requested/completed;
- policy evaluated/intent/fill.

No generic `timestamp` field substitutes for all clocks. Index/query on the clock relevant to eligibility or due scheduling.

SQLite time comparisons must use a consistent ISO parser/normalized representation; do not compare `T...Z` strings against space-formatted SQLite datetime strings lexicographically.

## 13. Backpressure

Measure queue lengths/ages by lane. Backpressure response:

1. preserve emergency/armed exits;
2. slow optional valuation/research;
3. reduce new entry preflight admissions based on capacity;
4. retain candidate/no-selection denominator;
5. never drop an admitted intent/fill/terminal silently.

Do not solve provider overload by only increasing timeouts/concurrency. Do not let one retrying no-route position starve others.

## 14. Recovery/idempotency

On restart:

- reload immutable active registrations/frontiers;
- rebuild current open positions/projections or validate snapshots;
- re-establish exact subscriptions for active surfaces;
- mark in-progress provider-only attempts interrupted/uncertain under their semantics;
- retry/replan only when policy permits;
- never duplicate intent/fill/position event;
- never reconstruct pre-activation history as current frames;
- ring-buffer baselines start with explicit warmup/left-censor state.

A restarted Reawakening detector cannot call the unobserved restart gap “dormancy”.

## 15. Storage observability

Persist/report:

- DB file/WAL sizes;
- write transaction p50/p95/max;
- busy/locked errors;
- WAL checkpoint duration;
- append rates by major table;
- projection update rate;
- Web query p50/p95;
- raw archive rate when enabled;
- retention/compaction actions and manifests.

Optimization is triggered by measured operational effect, not file size anxiety alone.

## 16. Retention rules

Never delete/compact away:

- registration/frontier/version definitions;
- cohort denominators;
- decisions/selections/propensities;
- intents/plans/attempts/fills/position events;
- dead/writeoff/error/no-route terminals;
- source rows referenced by a decision/frame;
- promotion/stop evidence.

Optional high-frequency non-decision telemetry may be rolled into fixed aggregates/cold archive under a versioned retention policy after its decision linkage and gap coverage are proven.

## 17. Parallelization

Safe parallel activities:

- passive discovery/collection;
- held-account subscriptions;
- local deterministic frame computation;
- at most two semantic Agent roles;
- read-only Web/snapshot serving;
- offline analysis on a read-only DB snapshot/connection.

Serialize or coordinate:

- SQLite writes through one Store owner;
- provider quote capacity through global scheduler;
- strategy version activation/frontiers;
- position/cash projection updates;
- future physical order submission.

Multiple Agents do not edit the same code/database. Codex remains the sole project writer during implementation.

## 18. Performance acceptance

Before adding new infrastructure, collect natural metrics and verify:

- held event callback-to-risk-state;
- risk-state-to-ExitIntent;
- intent queue/provider/terminal;
- MarketFrame receive-to-record;
- discovery-to-preflight;
- DB write p95 and busy errors;
- cockpit read p95;
- source gap/reconnect recovery;
- CPU/memory/network/storage growth.

If native WebSocket plus bounded transaction fetch meets the registered held-position SLO, do not deploy Yellowstone. If it does not, change only the transport while preserving frame/decision semantics.

## 19. Tests

- no network await occurs inside explicit Store write transaction for new paths;
- high-frequency events do not create one DB row per strategy;
- one frame/evidence row supports multiple decisions;
- projection rebuild equals current projection;
- Web hot endpoint uses bounded/materialized reads;
- backpressure pauses entries before exits;
- retrying position makes fair progress without lane monopoly;
- restart marks warmup/gaps and never invents dormant history;
- retention cannot remove referenced evidence/immutable terminals;
- all created files/temp/archive remain under the E project root.
