# V5 Operational Risk, Circuit Breaker and Recovery Specification

Date: 2026-09-04
Status: `P1/P2 OPERATIONS DESIGN / PAPER FIRST / FUTURE LIVE STRICTER`

## 1. Principle

Operational failure must not masquerade as market evidence or strategy behavior.

The default degradation hierarchy is:

1. preserve exact held-position observation and exits;
2. pause new entries;
3. pause optional valuations/research/enrichment;
4. preserve immutable failure/denominator records;
5. restore only after the exact failure condition is observed healthy under a registered rule.

`pause entries` never means `pause exits`.

## 2. Breaker scopes

### Global entry breaker

Blocks every new entry but leaves position/risk/exit/reconciliation active.

### Chain breaker

Blocks new entries on one chain; other chains/positions continue according to their own health.

### Venue/surface breaker

Blocks a program/router/surface decoder/version after a mismatch or protocol change.

### Strategy breaker

Stops new allocations for one policy/version due to accounting, tail or causal failure. Existing positions remain on their original policy/common hard-safety overrides.

### Provider lane breaker

Pauses/backs off one provider/client lane without declaring the market dead.

### Optional research breaker

Stops Agent, metadata, holder or fixed research to protect execution capacity.

### Future Live submission breaker

Stops new sends while confirmation/reconciliation ambiguity exists; does not erase already submitted transactions.

Every breaker is an append-only activation/release event with exact scope, reason, evidence and availability times.

## 3. Global entry-breaker triggers

Candidate engineering triggers, versioned before activation:

- duplicate Runtime/writer or violated single-instance lock;
- SQLite write failure, corruption/integrity failure, disk full or WAL/checkpoint state threatening durable order/account writes;
- system clock/monotonic-wall clock anomaly large enough to invalidate deadlines/available-at semantics;
- position/account projection mismatch that cannot be rebuilt from immutable fills/events;
- unresolved critical exit whose queue/attempt latency exceeds the registered emergency SLO;
- Jupiter/primary execution provider unusable beyond the registered failure window while positions require it;
- source/chain slot so stale that current execution plans cannot be trusted;
- code/schema/definition version mismatch;
- future Live ambiguous send/reconciliation/balance discrepancy;
- explicit local authorized operator command.

A single ordinary no-route for one token does not trigger a global breaker.

## 4. Chain/venue triggers

- RPC slot lag/gap beyond chain policy;
- wrong chain/genesis/chain ID response;
- official program/IDL/account-layout mismatch;
- route adapter returns structurally invalid plans;
- repeated simulation/account-decoder contradiction;
- token/venue exploit or emergency official deprecation known and available now;
- RWA registry unavailable/stale under a Robinhood policy that requires it;
- failure rate/latency beyond registered capacity thresholds.

The breaker status is evidence/operations, not a retroactive loss label.

## 5. Strategy breaker/stop

Immediate engineering stops:

- duplicate intents/fills/position events;
- cash/raw-amount invariant breach;
- future/late data contaminates a decision;
- strategy uses an unregistered feature/treatment;
- virtual/physical capital blending;
- provider work multiplied by policy count;
- hard exit overridden by positive Agent/context;
- surface state mislabeled safe.

Economic stops at registered checkpoints:

- tail/writeoff/drawdown budget breach;
- remove-best result reveals unacceptable winner dependence;
- entry expansion saturates exits/capital without robust gain;
- materially negative conservative economics across independent dates/clusters;
- Agent/Peak treatment increases tail or cannot operate before exits;
- model/calibration/drift failure.

A stop appends a new-entry frontier/status. It does not rewrite old policy rows or force old positions into a new soft exit; common safety/portfolio emergency rules still apply.

## 6. Operational state machine

`NORMAL -> DEGRADED -> ENTRY_PAUSED -> RECOVERING -> NORMAL`

Possible terminal/manual states:

- `VENUE_DISABLED`;
- `STRATEGY_STOPPED`;
- future `LIVE_SEND_DISABLED`;
- `MANUAL_HOLD`.

`DEGRADED` may reduce optional work/cadence before entry pause. The exact permitted actions are machine-readable by scope.

## 7. Recovery rules

Recovery is evidence-based, not timer-only:

- failing subsystem passes a bounded health/consistency probe;
- no critical exit/reconciliation remains unresolved;
- SQLite/account projection invariants pass;
- source/chain clocks are current;
- provider success/latency returns within the registered window;
- required subscriptions are re-established and gaps explicitly marked;
- version/config matches the active registry;
- local authorized command releases a manual breaker when required.

A breaker release is a new immutable event. Do not delete the activation.

For future Live, resuming entries requires explicit operator approval after ambiguous send/account mismatch; ordinary transient quote errors may auto-recover under the registered rule.

## 8. Exit behavior under degradation

### Jupiter/provider failure

- preserve ExitIntent and retry state;
- use a pre-registered alternate provider/route only if its semantics are fully defined;
- do not use stale DEX price as a fill;
- new entries pause when exit capacity/current sellability cannot be maintained.

### Held-account stream failure

- mark `DATA_STALE`;
- attempt bounded HTTP account refresh/re-subscribe;
- increase conservative route/recovery monitoring as capacity allows;
- pause entries requiring that safety source;
- do not declare rug solely from silence.

### DEX/provider mark failure

- local chain/account/route path continues;
- soft price/flow strategies may abstain or arm conservatively according to their version;
- exact account and execution exits remain.

### SQLite write failure

- no new provider/broker side effect whose attempt cannot first be durably recorded;
- future Live sender stops before send;
- open chain transactions already submitted enter external reconciliation after storage restores;
- Paper does not invent fills in memory.

## 9. Clock integrity

Strict-forward systems require clock diagnostics:

- monotonic duration for local queue/provider timing;
- UTC wall clock for cross-record availability;
- detect backward/large forward wall-clock jumps;
- record chain slot/block time separately;
- do not compare mixed ISO formats lexicographically;
- if wall-clock integrity is uncertain, pause new deadline-sensitive entries and preserve the anomaly.

A chain block time is not a substitute for local receive/available time.

## 10. Data-source disagreement

When route, exact accounts and provider marks disagree:

- preserve each fact/source/time;
- execution amount/minimum output remains economic authority for sellability;
- exact decoded account state remains structural authority for that account/surface;
- provider mark/liquidity is advisory;
- policy may arm/abstain under a registered contradiction rule;
- never average contradictory states into a fabricated “safe” value.

Material recurring contradictions can trigger a venue/decoder breaker.

## 11. Resource breakers

Monitor:

- CPU/memory/event-loop lag;
- disk free space/SQLite/WAL growth;
- browser/extension renderer memory for passive information collection;
- Agent subprocess/token budget;
- network/provider queue depth;
- Web query load.

Degradation order:

1. pause optional Agent/research;
2. reduce background hydration/valuation;
3. reduce new-entry preflights;
4. retain held/exits/durable order writes.

Do not kill a writer or in-flight execution task without recording interrupted/uncertain state.

## 12. Emergency portfolio action

Paper may support an authorized local append-only `REQUEST_PAPER_FLATTEN` command:

- creates full-remaining ExitIntents for every eligible open position;
- exact-account/emergency order remains first;
- quotes/fills use current execution semantics;
- no route remains explicit;
- command/actor/time/reason is audited;
- does not unlock or imply Live.

Future Live flatten requires a separately reviewed signer/submission path, amount/risk checks and reconciliation.

## 13. Web cockpit

Always show:

- current breakers by scope/state/reason/since;
- whether new entries are paused;
- exits/held monitoring status separately;
- oldest critical exit/uncertain attempt;
- source/clock/storage/provider health;
- recovery requirements;
- local/manual versus automatic origin;
- last immutable command/event.

A red global banner is reserved for actual operational risk, not ordinary losing PNL.

## 14. Notification priorities

1. future Live ambiguous send/balance mismatch;
2. exact-account emergency/critical exit overdue;
3. SQLite/order durability failure;
4. global/chain entry breaker;
5. held stream/data stale for open position;
6. strategy stopped/tail breach;
7. provider degradation;
8. optional research/source issue.

Repeated identical alerts are deduplicated by incident ID/state transition, while attempts/results remain append-only.

## 15. Tests

- entry pause leaves all exit/held loops active;
- DB write failure prevents side effect before durable attempt;
- one token no-route does not globally pause;
- critical exit overdue triggers configured breaker;
- source silence becomes DATA_STALE, not DEAD_TERMINAL;
- clock jump pauses deadline-sensitive entries and is recorded;
- wrong chain/program/schema triggers scoped breaker;
- recovery requires current evidence and appends a release event;
- strategy stop blocks only new allocations and keeps old exits;
- optional resource degradation yields to exits;
- public Web cannot release/activate breakers;
- local Paper flatten creates intents, not direct trades;
- no breaker can enable Live.

## 16. Implementation order

- Gate B: registry supports readiness/paused/stopped states;
- Gate C: durable attempt/idempotency and projection invariants;
- Gate E: entry-pause/exit-priority and risk-state integration;
- Gate K: cockpit/authorized local Paper commands;
- future Live: ambiguous-send/reconciliation/signer-specific breakers.

No broad breaker framework should delay Gates A-C. Implement only the fields/states required by the active tranche, preserving this contract for subsequent versions.
