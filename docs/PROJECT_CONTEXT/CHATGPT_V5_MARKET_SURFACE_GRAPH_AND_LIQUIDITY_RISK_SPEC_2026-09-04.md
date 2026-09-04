# V5 Market-Surface Graph and Liquidity-Risk Specification

Date: 2026-09-04
Status: `P1 DESIGN / CLARIFIES HOLDING-SURFACE TERMINOLOGY`

## 1. Conceptual correction

A spot Token position holds a token account balance, not an LP/pool position. The project’s established “Holding Surface Safety” means the safety/identity/liquidity facts of a selected **reference or primary market surface** associated with the token. It must not imply that the token is legally/technically custodied inside that pool or that every future execution must use it.

V5 uses:

- `token_position`: exact held mint/raw amount/cost;
- `reference_market_surface`: selected pool/pair used for current identity/features/monitoring;
- `execution_route_surface_set`: actual route legs for a specific BUY/SELL observation/plan;
- `known_market_surface_graph`: current locally observed pools/routes for the token, each with its own evidence/version/time.

The UI may retain the familiar “holding surface” label only if it explains this distinction.

## 2. Why one pair is insufficient

- Jupiter may buy/sell through different pools/venues over time;
- a multi-hop route can include unrelated quote/intermediate legs;
- DexScreener’s displayed pair may not appear in the actual route;
- one pool can be removed while another still provides an economic exit;
- a provider pair can remain stale/flat after its own liquidity disappears while the token trades elsewhere;
- a safe canonical pool does not prove unknown route legs safe;
- a malicious/removable pool is economically dangerous even if it was not the latest route.

Therefore all structural/economic claims are scoped to a specific surface or route observation.

## 3. Surface identity

Each surface record contains:

- chain;
- venue/program/router label;
- exact pool/pair/account when known;
- base/quote/intermediate mints and orientation;
- vault/LP/authority/creator lineage when decoded;
- canonical/noncanonical/opaque/unknown/invalid state;
- discovery/source/observed/available time;
- decoder/version;
- relation to launch/migration;
- first/last locally observed route use;
- current/terminal status.

Unknown/opaque surface is a first-class state, not coerced into a provider pair.

## 4. Surface graph

Nodes:

- token/quote/intermediate assets;
- exact pools/venues;
- opaque router segments;
- launch/migration events.

Edges:

- pool asset relation;
- current route leg/order;
- provider/display relation;
- canonical migration relation;
- alternative-route relation;
- replacement/new-surface relation;
- source/evidence lineage.

The graph is append-only evidence plus current projection. A later discovered surface does not become available to an earlier decision.

## 5. Reference surface selection

A strategy/version selects a reference surface from current facts, for example:

1. exact token-adjacent pool used by the current execution route when uniquely identified;
2. exact canonical migration pool when current/economically relevant;
3. exact provider pair if route relation is unknown, explicitly `display_reference_only`;
4. `none/opaque` when no valid exact surface exists.

Selection is deterministic, versioned and time-bound. Do not silently switch a prior position’s historical entry reference. Current monitoring can attach additional surfaces as new evidence events.

## 6. Route relation

For every amount-specific ExecutionObservation/Plan store:

- route legs/surface IDs or opaque segments;
- token-adjacent entry/exit surface where identifiable;
- whether the reference surface is included;
- route verifiability;
- central/minimum output and amount;
- request/context/response time;
- alternative surface count/known coverage.

The economic authority is the current amount-specific output, not the existence of one surface.

## 7. Liquidity-risk states by surface and token position

### Surface states

- `SURFACE_HEALTHY_OBSERVED`;
- `SURFACE_LIQUIDITY_DEGRADING`;
- `SURFACE_ACCOUNT_ALERT`;
- `SURFACE_DEAD_TERMINAL`;
- `SURFACE_DATA_STALE`;
- `SURFACE_UNKNOWN/OPAQUE`;
- `SURFACE_REPLACED_BY_NEW_SURFACE` (historical relation, not recovery of old surface).

### Token-position aggregate states

- `ECONOMIC_EXIT_AVAILABLE`;
- `EXIT_DEGRADED`;
- `REFERENCE_SURFACE_ALERT_BUT_ALTERNATIVE_ROUTE`;
- `NO_CURRENT_ROUTE_TRANSIENT`;
- `EXACT_ALERT_AND_NO_ECONOMIC_ROUTE`;
- `POSITION_DEAD_TERMINAL` under the registered predicate;
- `UNKNOWN_DATA/EXECUTION`.

A surface alert can immediately arm a full-position exit. If an alternative route is economic, fill through it and close/reduce. Do not require the sell to return through the alerted/reference pool.

## 8. Terminal semantics

Keep the current core rule:

- an exact structural account/pool alert by itself triggers the highest-priority escape attempt;
- a current full-remaining amount quote/route determines whether an economic exit exists;
- only the registered combination produces position writeoff/dead terminal;
- one provider no-route, price flat or displayed liquidity zero alone is not enough;
- after a surface is confirmed dead, that exact surface/version never re-arms as healthy.

If another surface later appears:

- it is a new market surface/evidence event;
- it does not rewrite the old surface’s death or old position PNL;
- a future new cohort/re-entry requires an explicit strategy rule and no applicable mint/surface/policy no-reentry terminal;
- the risk relation to the earlier dead surface remains visible.

## 9. Pretrade use

### Strong tier

- exact current reference surface;
- direct mint/control facts;
- current route relation;
- two-way amount-specific execution;
- exact watcher possible.

### Paper exploration tiers

- exact noncanonical/creator-controlled surface;
- route excludes the displayed/reference pair but route legs are known;
- opaque/multi-hop surface relation;
- exact surface unknown but mint/two-way route valid.

Each tier has explicit Paper role, monitoring degradation and Live false where applicable. No tier borrows another pool’s safety result.

## 10. Post-entry monitoring

Share by exact surface/token:

- account/vault/LP subscriptions for every materially relevant exact surface within capacity;
- PumpSwap flow frames per exact pool;
- current route surface observations;
- token-level full-position recovery;
- provider pair marks as advisory.

Priority:

1. surfaces on current/recent economic exit routes;
2. reference/canonical surface;
3. surfaces with exact risk alert;
4. other observed alternatives as bounded research.

Do not subscribe once per virtual strategy.

## 11. Price-stall interpretation

For a provider/reference pair whose price stops changing:

- verify source heartbeat/update count;
- inspect exact pool swaps/account changes when known;
- inspect token-level route/recovery through all current routes;
- classify pair-level market stall versus data stale;
- arm an exit under policy when risk/recovery warrants;
- never generalize the pair’s flat line to “Token cannot trade anywhere” without execution evidence.

This directly incorporates the user’s valuable observation while avoiding false pool-death declarations.

## 12. Portfolio and clustering

Several positions in the same mint/surface graph are one correlated physical risk. Report/cap:

- token/mint exposure;
- exact surface exposure;
- route/provider dependence;
- shared creator/cluster;
- alternative-route concentration.

Twelve virtual policies do not multiply exact subscriptions or diversify the market risk.

## 13. Web presentation

Token/position detail shows:

- held Token mint/raw amount;
- reference surface and classification;
- current BUY/SELL route surfaces;
- alternative routes/surfaces;
- exact account/vault alerts;
- provider/display pair relation;
- full-position executable recovery;
- surface terminal/new-surface history.

Use labels such as:

- `REFERENCE MARKET SURFACE`;
- `CURRENT EXECUTION ROUTE`;
- `POOL SAFETY KNOWN/UNKNOWN`;
- `ALTERNATIVE EXIT AVAILABLE`;
- `SURFACE DEAD — TOKEN MAY HAVE OTHER SURFACES`.

Do not say “position is in this pool”.

## 14. Tests

- displayed pair absent from route remains explicit;
- safe reference pool cannot mark opaque route safe;
- reference pool alert plus alternative economic route fills, not writes off;
- exact surface dead remains dead after a new pool appears;
- new surface does not rewrite old PNL/cohort;
- flat/stale provider pair does not imply token-level no route;
- opaque surface never receives exact watcher/canonical label;
- one surface subscription serves multiple virtual policies;
- route can change between BUY and SELL without corrupting position identity;
- full-position execution remains amount-specific and current;
- no reentry rule is scoped exactly to its mint/surface/policy contract.

## 15. Integration

- Gate B/C: schema fields distinguish token position, reference surface and execution observation;
- Gate D: surface tiers/risk buckets;
- Gate E: aggregate token-position risk versus individual surface alerts;
- Gate F/G: exact pool flow and route-quality features;
- Gate K: graph/labels;
- Gate L: equivalent EVM venue/surface graphs with chain-specific facts.
