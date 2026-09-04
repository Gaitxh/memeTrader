# V5 Launch Recall — Pump Bonding Curve to AMM Transition Specification

Date: 2026-09-04
Status: `GATE D/F DESIGN / JUPITER-ROUTE FIRST / NO DIRECT PUMP BROKER IN GATES A-C`

## 1. Objective

Capture and compare the earliest executable Pump.fun launch opportunities across two distinct market phases:

1. active Pump bonding curve before completion/migration;
2. migrated AMM/PumpSwap market.

Do not define “launch” as only the post-migration pool. Do not pool the two phases into one undifferentiated sample or copy an AMM custody model onto a bonding-curve account.

## 2. Phase states

For each token/surface lineage, persist current available state:

- `CREATE_OBSERVED_PROVIDER_ONLY`;
- `MINT_AND_CURVE_CHAIN_VERIFIED`;
- `BONDING_CURVE_ACTIVE`;
- `BONDING_CURVE_COMPLETE_PENDING_MIGRATION`;
- `MIGRATION_OBSERVED_PROVIDER_ONLY`;
- `MIGRATION_CHAIN_VERIFIED`;
- `AMM_SURFACE_ACTIVE`;
- `UNKNOWN/CONFLICT/STALE`.

State is append-only events plus current projection. A later verified transition cannot be backfilled into an earlier decision.

## 3. Cohort identity

Launch Recall subcohort key:

`(entry_family_version, token_mint, entry_phase, phase_surface_id_or_explicit_unknown, launch_episode_id)`

Entry phase is frozen at decision/fill. Later migration does not relabel a bonding-curve entry as an AMM entry.

A strategy may enter at most once per token/entry-family version in the first Launch Recall policy, unless a later separate re-entry/transition strategy is registered. Migration itself does not automatically create another position.

## 4. Entry requirements on the bonding curve

Common hard requirements:

- exact Solana token mint/program/decimals and deterministic transfer validity;
- current phase/account lineage available under the registered source/version;
- no applicable terminal mint/surface/policy no-reentry;
- current amount-specific 20 USDC BUY quote through Jupiter/registered adapter;
- `SAME_STATE_REVERSE_SELLABILITY_PROBE` for the conservative acquired amount;
- timing/route/cost/evidence-class validity;
- capital/exit-capacity selection.

Exact curve account/program state is strongly preferred and required for any structural-safety claim. A provider-only/opaque route can be a bounded Paper exploration tier only, safety unknown and Live false.

No current reverse route means research-only/no executable Paper fill in the first version.

## 5. Entry requirements after migration

Use the same v5 common execution contract, plus current AMM surface classification:

- exact canonical PumpSwap;
- exact noncanonical pool;
- opaque/unknown route surface;
- invalid/mismatch.

Risk bucket/monitoring/Live eligibility remain explicit. Do not require the route to use the displayed/canonical pool merely for presentation, but do not borrow one pool’s safety facts for another route.

## 6. Create events and quote budget

Every create event enters the Full Opportunity Shadow/census when valid, but expensive Jupiter preflight is bounded.

Cheap preflight ordering may use only current facts:

- exact phase/account readiness;
- event age/deadline;
- first locally observed economic activity;
- current provider snapshot when fresh;
- creator-history/risk bucket;
- surface/route availability hints;
- deterministic exploration assignment;
- remaining exit/quote capacity.

A create with no current market/route readiness remains pending or reaches a registered no-route/expired terminal; it must not repeatedly monopolize the quote lane.

Migration/current transaction events can invalidate/reprioritize the pending opportunity because they are new available facts.

## 7. Surface transition after an open bonding-curve entry

The token position remains the same mint/raw amount/cost. Append a transition event:

- old curve phase/surface and terminal/completion state;
- migration signature/slot/source/available time;
- new AMM surface candidates/verification;
- current route observation;
- watcher subscription changes;
- data gap/unknown state.

Do not close/reopen the Paper position or realize PNL merely because migration occurred.

The position’s current reference-market-surface projection may move to the new verified AMM surface, while the original entry phase/lineage remains immutable.

## 8. Exit during transition

Migration can produce temporary route changes/no-route/volatility. Policy behavior is versioned:

- exact account/route risk can arm an exit;
- a current alternative economic route may fill;
- transient no-route receives bounded retry according to urgency;
- absence of an AMM surface immediately after curve completion is not automatically a rug/writeoff;
- terminal dead semantics require the exact registered structural/economic predicate;
- maximum hold and common portfolio breaker still apply.

The transition must not block critical exit work while waiting for metadata or Agent investigation.

## 9. Monitoring

### Bonding curve

Share subscriptions/observations for:

- exact bonding-curve/global/program accounts needed by the official interface;
- mint/token controls;
- relevant transaction/log flow;
- current amount-specific route/recovery;
- source gap/phase completion.

### AMM

Attach:

- exact pool/base/quote vault/LP/mint accounts when identified;
- PumpSwap flow MarketFrame;
- route/surface graph;
- current full-position recovery.

Never subscribe per virtual strategy.

## 10. Features and comparisons

Record subcohorts:

- curve entry age/progress/liquidity state;
- migration proximity/current completion signal available then;
- first trade/flow/breadth/concentration;
- same-state reverse-probe recovery;
- route complexity/surface exactness;
- creator history;
- transition latency/gap;
- AMM first-flow/route recovery after migration.

Compare all-cases outcomes separately:

- bonding-curve entries that exit before migration;
- entries held through migration;
- post-migration AMM entries;
- create events that never obtain an executable route;
- migration failures/long gaps/no-route/dead cases.

Do not select only tokens that successfully migrate.

## 11. Causal/selection risks

- conditioning on migration creates survivorship bias;
- using final curve completion time/progress before it was observed leaks future information;
- tokens with no route/failed migration must remain in the create denominator;
- early quote coverage is selected by scheduler/provider availability;
- provider create/migration time may differ from direct chain availability;
- the same token across phases is correlated, not two independent samples;
- a later profitable AMM path cannot validate an earlier curve entry without the full cohort.

## 12. Direct Pump adapter boundary

First v5 Launch Recall uses the existing/current Jupiter execution path when it supports the phase/token amount. Do not add a direct Pump instruction builder/signing adapter inside Gates A-C or merely to increase Paper counts.

A future direct adapter is considered only if current forward data shows meaningful bonding-curve opportunities are systematically not addressable through Jupiter and the official program interface supports a complete amount/fee/slippage/build/simulation/exit path. It requires a new execution adapter/version and the same Paper/Live authority boundaries.

## 13. Web

Token/position timeline shows:

- create/curve verification;
- entry phase;
- curve progress/state available at each time;
- migration provider/direct verification;
- reference-surface transition;
- current route/recovery;
- no-route/gap/watcher changes;
- strategy fill/exit.

Labels:

- `ENTRY: BONDING CURVE`;
- `ENTRY: POST-MIGRATION AMM`;
- `HELD THROUGH MIGRATION`;
- `MIGRATION NOT YET VERIFIED`;
- `SURFACE TRANSITION — POSITION NOT REOPENED`.

## 14. Tests

- later migration cannot relabel/backfill bonding-curve entry;
- create without route stays in Shadow/no-fill denominator;
- same token is not automatically bought again at migration;
- position raw amount/cost persists across surface transition;
- provider-only migration is not direct chain verification;
- curve account rules are not replaced by AMM pool rules;
- transition no-route is not automatically terminal rug;
- exact current alternative route can exit during transition;
- subscriptions/quotes are shared across virtual policies;
- post-migration winner does not remove failed/nonmigrated create cases;
- Live remains locked.

## 15. Integration order

- Gates A-C: registry/lifecycle fields support `entry_phase` and surface-transition events; no active strategy;
- Gate D: Launch Recall Fast/Balanced may activate for route-supported bonding-curve and AMM subcohorts with separate reporting;
- Gate E: transition-aware exit/risk;
- Gate F: exact transaction/account flow and phase state;
- Gate J: compare entry phase/held-through-migration effects under full denominators.
