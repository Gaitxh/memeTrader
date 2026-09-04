# V5 Discovery Fast Lane and End-to-End Latency Specification

Date: 2026-09-04
Status: `P1 DESIGN / SOLANA FIRST / DOES NOT BLOCK GATES A-C`

## 1. Objective

Convert a new launch/migration/flow event into a strict-forward executable decision quickly enough to capture opportunity, without waiting for slow metadata, social research or background hydration and without starving exits.

The product latency path is:

`source event -> durable launch/opportunity -> minimal current facts -> strategy decisions -> shared BUY/acquired-quantity SELL preflight -> portfolio selection -> OrderIntent/Paper Fill`

Each component has separate clocks and failure states.

## 2. Source hierarchy

### Immediate leads

- Pump/PumpSwap on-chain program logs/accounts using the official interface/IDL;
- current PumpPortal create/migration feed as a provider observation/low-latency lead;
- first locally observed PumpSwap transaction/account state;
- current Jupiter route/preflight.

### Background/enrichment

- DexScreener/Gecko hydration;
- metadata URI/site/social links;
- passive news/social evidence;
- holder/creator/wallet features not already local;
- optional Agent research after fill.

The fast path may proceed with explicit missing optional fields. It may not proceed without exact mint, current executable route contract or deterministic transfer validity required by its Paper role.

## 3. Provider lead versus chain truth

A PumpPortal event can trigger immediate work, but preserve:

- provider observed/received/recorded clocks;
- signature/mint/creator/event type;
- later direct chain verification and its availability time;
- mismatch/missing/timeout terminal.

A later chain confirmation does not become available at the earlier provider decision. Strategies declare whether provider-observed launch lineage is sufficient for a Paper risk bucket or direct chain verification is required.

## 4. Fast opportunity object

On the first eligible lead, atomically append:

- opportunity/cohort ID;
- chain/mint/source event/signature/slot;
- source and local availability times;
- entry-family candidates;
- initial surface/route state (`unknown` allowed as a risk state, not safe);
- fast-lane deadline/version;
- dedupe key;
- required minimal tasks;
- optional enrichment pending flags.

Do not wait for full Token row hydration to create the opportunity. Link the eventual hydration row by ID/version.

## 5. Minimal deterministic facts

Prioritize local/cache/RPC facts needed for execution:

- valid Solana address/mint and program owner;
- decimals/supply/mint/freeze/Token-2022 extensions;
- launch/migration/pool candidates and exact/opaque state;
- quote asset relationship;
- current account/source freshness;
- cheap current market activity/flow summary if already available;
- terminal no-reentry lookup;
- current capital/exit capacity.

Fetch related immutable mint/pool accounts with `getMultipleAccounts` or an equivalent bounded batch when it reduces RPC round trips and preserves per-account clocks/results.

## 6. Work queues

### `EXIT_CRITICAL`

Exact-account/armed exits. Always first.

### `ENTRY_FAST`

New opportunity before its registered deadline. Contains only minimal fact and shared preflight work.

### `POSITION_NORMAL`

Open-position frames/valuation.

### `OUTCOME_FIXED`

Registered fixed-horizon outcomes.

### `ENRICHMENT_BACKGROUND`

Metadata/social/holder/creator expansions and optional research.

Within a lane use earliest deadline and deterministic fairness. Background backlog cannot delay current launch or exit.

## 7. Fast-lane stages and clocks

Record:

1. source observed/received;
2. durable opportunity created;
3. minimal identity/mint facts ready;
4. strategy evaluation ready;
5. quote queued/requested/completed;
6. reverse preflight queued/requested/completed;
7. portfolio selected;
8. intent/fill/terminal.

Each stage has status:

- success;
- missing/unknown;
- no-route;
- stale/late;
- provider/RPC error;
- capacity skipped;
- duplicate;
- invalid;
- interrupted.

Do not report one aggregate latency that hides a 15-minute hydration delay or provider queue.

## 8. Latency objectives

Use current measured distributions before freezing numerical SLOs. Initial engineering targets may follow the existing focus experience but must be registered:

- source-to-durable opportunity: sub-second/low seconds when the source itself is live;
- minimal facts: bounded low seconds;
- entry quote queue <= a small current deadline;
- final BUY+SELL preflight total compatible with the entry family’s age/deadline;
- exact-account alert to ExitIntent substantially faster than ordinary loops.

Missed SLO remains in the cohort as `late/capacity/provider` and does not trigger a later backfilled trade.

## 9. Connection and computation reuse

- persistent HTTP/RPC/WebSocket clients;
- host rate-limit/capacity controller shared with exits;
- immutable mint/decimals/account facts cached by version;
- one program/log subscription filtered locally rather than one subscription per strategy;
- one exact pool/account subscription shared by every position/allocation;
- one quote/preflight for exact-identical strategy contracts;
- incremental features, no repeated full-history scans;
- source-fact/Agent single-flight.

No browser/Web request triggers the fast lane.

## 10. Discovery prioritization

Token supply is much larger than quote capacity. Before expensive preflight:

- prioritize migration/new AMM/first-current-flow events;
- use cheap current activity and risk-bucket/fair exploration ordering;
- reserve some deterministic low-score audit samples;
- dedupe same token/surface/episode;
- enforce exit-capacity headroom;
- record every capacity/priority not-selected reason.

Do not use metadata/social completion as the default ranking prerequisite.

## 11. Failure recovery

- source disconnect creates gap/heartbeat state;
- reconnect never fabricates missed opportunities as live entries;
- newly received old events may enter audit/outcome only according to version;
- in-progress attempt is recovered through immutable attempt semantics;
- old hydration backlog does not regain priority over fresh fast-lane items;
- transient provider failure uses bounded backoff/deadline;
- exhausted/late entries terminate rather than chasing an already-moved token indefinitely.

## 12. Relationship to MarketFrame

Before full transaction flow decoder:

- Launch Recall can use the minimal provider/current facts with explicit source quality;
- Fast/Balanced exits use current executable route/account/provider signals.

After MarketFrame:

- Flow Acceleration uses transaction-derived crossing;
- Launch risk/breadth improves;
- PeakGuard and Reawakening activate.

The decoder enriches the fast lane; it does not require the entire architecture to wait.

## 13. Web/observability

Display:

- source events/minute and last event;
- fast opportunities created;
- stage conversion and latency p50/p95;
- current oldest fast entry;
- late/capacity/no-route/mint-invalid counts;
- background backlog separately;
- exit capacity utilization/headroom;
- last discovery sequence pulse.

A high discovery count with zero preflight is visibly a pipeline/capacity issue, not “strategy cautious”.

## 14. Tests

- new event creates durable opportunity without metadata hydration;
- duplicate provider/on-chain representations dedupe but preserve provenance;
- background FIFO cannot delay fast entry/exit;
- one mint-account batch preserves individual terminal states/times;
- source reconnect/backfill cannot create a live entry before availability;
- same opportunity does not request duplicate quote per strategy;
- exit preempts fast entry;
- capacity skip remains in denominator;
- stale/late quote cannot fill;
- no Web endpoint starts RPC/Jupiter work;
- all storage/temp remains under E project root.

## 15. Acceptance

- natural new launch/migration reaches each fast-lane stage with measured latency;
- at least one success and natural failure/late/no-route terminal are preserved when observed;
- exits remain within their registered priority/SLO under discovery bursts;
- metadata/background work continues without controlling entry timing;
- no future/backfill/duplicate provider work;
- Live remains locked.
