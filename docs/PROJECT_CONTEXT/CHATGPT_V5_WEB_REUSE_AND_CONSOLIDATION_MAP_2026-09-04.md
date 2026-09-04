# V5 Web Reuse and Consolidation Map

Date: 2026-09-04
Status: `PRODUCT MIGRATION MAP / REUSE DATA/COMPONENTS, NOT OLD SEMANTIC ERRORS`

## 1. Current surfaces

The project currently exposes two useful but overlapping Web concepts:

- the broad memeTrader Web console with Events, Tokens, Decisions, Portfolio/Wallet, Sources, Agents, Audit/Learning and Settings;
- the focused ChainMemeTrader surface with runtime pulse, Token discovery, 12-stage cards, equity/positions/trades, risk events and Token detail.

The user is correct that the broad memeTrader Web contains valuable operational/research components. V5 should converge toward one coherent navigation/data model rather than maintain two competing product truths indefinitely.

Immediate Gates A-C only correct semantic labels and expose v5 readiness. Full consolidation belongs to Gate K after the v5 execution/risk entities exist.

## 2. Components to reuse directly or adapt

### Navigation/deep-link utilities

Reuse/adapt:

- Token deep links/details;
- Event/source links and provenance role display;
- transaction/explorer links when allowlisted;
- bilingual labels/utilities;
- responsive navigation shell;
- safe URL/text escaping and field allowlists.

V5 additions:

- OrderIntent/Plan/Attempt/Fill deep links;
- position/risk state and exact pool/account lineage;
- strategy definition/frontier/version links;
- cohort/paired comparison links.

### Runtime and health presentation

Reuse/adapt:

- Runtime/SQLite/collector health cards;
- last-success/last-item times;
- source stale/error distinctions;
- loopback/public access and Live-lock banners;
- scheduled task/single-process status.

V5 correction:

- every pulse is sequence/time driven by real persisted work;
- process/listener alive is not enough;
- market quiet, collector stale, disabled and error remain distinct;
- exit lane and held-account subscriptions are first-class health items.

### Token discovery and funnel

Reuse/adapt:

- Token discovery exposures;
- first-local-discovery counts;
- hydration status;
- full-universe DAG/attempt/failure accounting;
- Token stream/detail drawer.

V5 correction:

- show discovery→fast opportunity→frame→strategy decision→preflight→portfolio selection→fill→exit;
- raw discoveries are not trades;
- capacity/not-selected and research-only outcomes are visible;
- no forced single linear conversion when paths differ.

### Equity/position truth

Reuse/adapt:

- existing separation of executable versus indicative valuation;
- amount-specific remaining-position quote status;
- cash/realized/open-position cards and curves;
- null/unknown rather than fake zero;
- position tables and recent fills.

V5 correction:

- conservative minimum-output, central quote and future Live-reconciled layers separated;
- twelve virtual accounts are not additive physical capital;
- exact paired policy allocations and distinct token/cohort counts shown;
- critical risk sorting precedes attractive gains;
- cost-completeness state is prominent.

### Notification/alert center

Reuse/adapt:

- allowlisted normalized records;
- group/severity/action/reason/time;
- Paper/simulation badges;
- stale-stream state;
- links to events/tokens.

V5 additions:

- exact-account emergency;
- ExitIntent/quote/fill/writeoff;
- data/market stall distinction;
- execution lane late/blocked;
- strategy activation/pause/promotion;
- reconciliation status in future Live.

Critical operational alerts appear on the cockpit first, not only inside the notification page.

### Source/evidence/research pages

Reuse/adapt:

- source role/provenance/revision/independence display;
- exact post/event/Token relation lineage;
- information-first and Token-context forward ledgers;
- no-decision attribution;
- full-universe/fixed-horizon outcomes;
- Agent admission/cost/failure evidence;
- audit/history views.

V5 role:

- these become deep Research/History pages and post-buy evidence links;
- they do not dominate the execution cockpit;
- old S1/S2/S3/WATCH/v1–v4 remain visible and immutable;
- passive information evidence can accelerate shared post-buy cases.

### Strategy contract/version presentation

Reuse/adapt:

- machine-readable strategy family/policy/cost/execution fields;
- activation/promotion state;
- version history;
- runner/treatment state;
- maturity labels.

V5 correction:

- v4 cumulative stages move to History;
- v5 policy ID, entry family, exit/treatment, readiness and paired control are explicit;
- `REGISTERED`, `ACTIVE`, `ADVISORY`, `FEATURE_PENDING`, `BASELINE_BUILDING`, `PAUSED`, `STOPPED` and `MATURE` are not collapsed;
- no immature ranking.

## 3. Components/semantics not to carry forward

- a homepage wall of all 12 strategy cards;
- v4 wording that says every Stage has the same entry;
- rank numbers for sparse/incompletely valued arms;
- combined totals across independent virtual accounts;
- DEX indicative marks presented next to executable PNL without a strong boundary;
- a green “healthy” indicator based only on port/listener/process;
- browser-triggered Jupiter/RPC/Agent work;
- research ledgers above critical exit/position state;
- mutable strategy parameters presented as ordinary settings;
- separate inconsistent cost/Live labels between the two Web apps.

## 4. Recommended canonical information architecture

Long term, one canonical shell/backend contract:

- `/cockpit` — focused real-time operation;
- `/strategies` — v5 policies/accounts/comparisons;
- `/positions` — risk/executable recovery/exit work;
- `/execution` — intent/plan/attempt/fill;
- `/tokens/:id` and `/events/:id` — deep lineage;
- `/risk` — account/stall/route/dead/no-reentry;
- `/learning` — ablations/paired outcomes/models/Agent treatment;
- `/sources` — passive information/collector provenance;
- `/chains` — chain adapter maturity;
- `/system` — processes/queues/storage/providers;
- `/history` — old S1/S2/S3/WATCH/v1–v4 and audits.

Whether the final listener is the current broad Web port or the focused Chain Web port is an implementation decision after measuring integration cost. The product must expose one canonical navigation and one schema/version truth. A temporary deep link between the two is acceptable; duplicate strategy/equity calculations are not.

## 5. Incremental migration

### Gates A-B

- relabel v4 as historical cumulative evolution;
- add v5 registry/readiness view;
- no v4/v5 combined rank;
- preserve current functional pages.

### Gates C-E

- expose StrategyDecision/ExecutionObservation/VirtualFill/PositionEvent/ExitIntent lineage;
- critical banner and risk-first open positions;
- conservative/central/unknown cost/equity truth;
- current queue/capacity.

### Gates F-I

- MarketFrame/flow/Peak advisory detail;
- Reawakening baseline/crossing timeline;
- shared Agent case/evidence/advisory/treatment timing.

### Gate J-K

- mature ranking and paired comparisons;
- propensity/gate-ablation/cluster robustness;
- real persisted pulses/activity cursor;
- consolidate canonical shell/routes;
- performance and browser QA.

### Gate L

- BSC/Robinhood chain panels with separate execution/cost/safety maturity;
- no cross-chain blended PNL when cost completeness differs.

## 6. Cockpit reuse layout

Above fold:

1. Live lock/current epoch/version/time;
2. exact-account/exit-lane critical banner;
3. reused/adapted health/pulse strip;
4. executable cash/equity/unknown/worst-case cost;
5. open-position risk board;
6. discovery→execution funnel and recent intent/fill stream;
7. mature Top 3 or `LEARNING / UNRANKED`.

Below fold/deep links:

- full strategy matrix;
- source/events/research;
- versions/history;
- storage/system diagnostics.

## 7. One backend truth

Do not duplicate calculations in JavaScript or across two Python Web servers. Current projections are produced by Store/Runtime and read by Web:

- account snapshots;
- current position risk/executable valuation;
- queue/capacity;
- pulse sequence/last times;
- maturity/rank snapshot;
- bounded recent activity.

Both temporary Web surfaces may read the same schema while migration occurs. The frontend does not infer a dead pool, fill, PNL or strategy maturity.

## 8. Visual behavior

- color plus text/icon, not color alone;
- real event sequence drives motion;
- reduced-motion support;
- exact timestamps/age visible;
- empty/loading/stale/error/disabled differentiated;
- dangerous positions remain pinned/sorted first;
- research cards default collapsed on the cockpit;
- mobile shows critical exits/positions before charts.

## 9. Browser QA

For each coherent release:

- local and protected public read-only access;
- Chinese/English labels;
- desktop/mobile widths;
- console/network errors;
- current sequence/poll/SSE gap behavior;
- critical alert visibility;
- unknown/null valuation;
- v4/v5 separation;
- no provider/RPC calls from browser;
- bounded response/render time with current large SQLite.

Do not run broad visual work for every backend edit; reserve full QA for a coherent Web release boundary.

## 10. Acceptance

- one canonical current strategy/equity truth;
- v4 historical/open-legacy and v5 current policies clearly separated;
- existing valuable event/source/token/audit detail remains reachable;
- critical execution/risk state outranks research content;
- mature Top 3 only, otherwise unranked;
- real pulses, not decorative animation;
- no duplicated provider work/calculation;
- responsive, bilingual and truthful;
- Live remains locked.
