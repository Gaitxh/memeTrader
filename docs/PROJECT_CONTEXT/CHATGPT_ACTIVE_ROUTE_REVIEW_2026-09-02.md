# ChatGPT → Codex route-stage review · 2026-09-02

Status: `PENDING_CODEX_VERIFICATION`

Scope: active `kol-token-addressability-route/v1` implementation observed while Codex was adding its Store/Runtime/tests. This is a read-only independent review of the changing checkout. Re-read current bytes before acting.

## What is directionally correct

- Reuses the existing quote-only Jupiter client rather than creating a swap/transaction path.
- Writes the attempt before the provider call and appends a result afterward.
- Uses an append-only registration/attempt/result/confirmation ledger with `decision_eligible=0` and `affects=none`.
- Uses the existing shared Jupiter lock and processes at most one addressability route per invocation.
- Retains explicit no-seed, no-route, unsupported-chain, protocol-invalid, error, missing-pair, queue/interruption and surface-unmapped states.
- Keeps Paper/Decision/Position/Trade out of this path.

These are necessary but not sufficient for a valid route-lag estimand.

## Blocking findings

### R0-A · Quote completion after the deadline is currently counted as quoted success

`start_kol_token_addressability_route_attempt()` rejects a request started after `deadline_at`, but `record_kol_token_addressability_route_result()` does not compare the actual provider/local `completed_at` with `deadline_at`. A request started one millisecond before the cutoff and returned well afterward is currently recorded as `quoted_surface_match` or `quoted_surface_unmapped`.

Required semantics:

- freeze and store `deadline_at` in the attempt/result evidence;
- validate `requested_at <= completed_at` and use the durable local completion clock;
- classify `completed_at > deadline_at` explicitly, for example `quoted_late_surface_match` / `quoted_late_surface_unmapped`, or one `route_late` state plus surface classification;
- only a completed quote by the deadline may satisfy timely `T_route_available`;
- add a deterministic test covering request-before / completion-after.

### R0-B · A Dex pair that first appears after the deadline is mislabeled as queue delay

`due_kol_token_addressability_routes()` selects the first `dex_pair_available` milestone. When it exists and the current evaluation is after the route deadline, the code records `queue_delay_expired` without checking `pair.available_at`.

This conflates two different failures:

1. `dex_pair_late`: the pair itself was not locally available by the route deadline;
2. `queue_delay_expired`: the pair was available in time, but the local scheduler did not start the quote in time.

Required test cases:

- pair available before deadline, tick after deadline → queue delay;
- pair available after deadline → pair late, never queue delay;
- no pair by deadline → missing by deadline;
- pair available and request/response complete before deadline → timely route result.

### R0-C · Registration parsing must fail closed, not throw out of the periodic task

`due_kol_token_addressability_routes()` directly `json.loads()` the registered definition and directly indexes required keys. A malformed/unsupported frozen row can throw on every five-second periodic invocation. `refresh_kol_token_addressability_evidence()` also takes the confirmation window from a mutable class constant instead of the frozen route definition.

Required direction:

- one strict parser/validator for the registered route definition;
- verify version, activation policy, router, input mint/amount, slippage, route deadline, confirmation window, same-surface policy, `decision_eligible=false`, `affects=none`;
- malformed/unsupported definitions fail closed and create no provider request; surface one bounded operational error rather than a retry storm;
- all route and confirmation behavior comes from the parsed registration, not class constants.

### R0-D · “Independent confirmation” is presently only a cross-origin exact-CA mention

The current confirmation scan requires another origin and the same Event, but it accepts any `feature`/`confirmation` observation containing the address. It does not prove factual independence and does not exclude promotion, identity-only/project self-description, syndication or copied content. Raw substring matching can also accept an address embedded inside a longer alphanumeric string.

Do one of the following, explicitly:

- rename the milestone/result to `cross_origin_exact_ca_mention`, keeping it descriptive; or
- require current point-in-time provenance/claim-assessment evidence that meets the existing independent-content/factual-confirmation rule.

Also use the canonical exact-address extractor/boundary rules rather than arbitrary substring containment. A different URL/domain is not automatically independent evidence.

### R0-E · No-seed episodes still cannot acquire a later exact identifier

A `no_seed_at_signal` cohort immediately receives no-seed route/confirmation terminals and is skipped forever because `identifiers_json` is immutable and empty. Therefore the current implementation cannot measure `T_signal → T_explicit_identifier` for the very cases whose lag is most important.

Do not mutate the cohort. Add an append-only exact-identifier discovery ledger linked to the cohort and a naturally arriving observation, with:

- same-episode lineage established only from point-in-time evidence;
- exact CA and chain context;
- source observation ID and durable availability times;
- ambiguity/zero/late terminals;
- no ticker/alias search and no later winner selection.

Until that exists, report no-seed as a retained denominator but describe the implemented estimand as **signal-time exact-CA route lag**, not full addressability lag.

### R0-F · Generic EVM addresses remain chain-ambiguous

The base cohort stores an EVM CA as chain `evm`, while discovery searches every non-Solana chain. Same 20-byte address across Base/BSC/Ethereum/etc. may produce multiple Token/pair milestones. The route ledger currently reduces all non-Solana cases to `unsupported_chain`, which preserves a terminal but does not resolve or record the actual chain ambiguity.

Preserve all chain candidates and write an explicit ambiguity result. Never describe a generic `0x…` address as uniquely addressable without contemporaneous chain evidence.

### R0-G · `tokens.first_seen_at` remains an unsafe local-availability clock

Both initial enrollment and refresh still use `tokens.first_seen_at`. That column can be populated from a caller/provider observation time and is not guaranteed to equal the first durable local record time. This can make `T_local_token_discovery` appear earlier than the machine actually knew the Token.

Use an immutable local exposure/snapshot/transition `recorded_at` (with valid observed ≤ ingested ≤ recorded ordering), or retain the milestone as unknown. Provider historical time may be descriptive but cannot establish local availability.

### R0-H · `quoted_surface_unmapped` must not satisfy same-surface success

A valid Jupiter quote whose route cannot be linked to the frozen Dex surface proves some Solana route existed, but it does not prove the frozen pair was executable. Keep it in the denominator as descriptive `route_found_surface_unmapped`; exclude it from same-pair/same-surface success and from any same-surface 15/60/240 outcome.

For split or multi-hop routes, finding the pair address in any `amm_key` proves that pool participated, not necessarily that the whole route is the same frozen surface. Freeze and state the exact success definition before summaries are implemented.

## Runtime/SQLite boundedness

`refresh_kol_token_addressability_evidence()` currently scans every post-activation cohort, every identifier, matching Token rows, snapshots and same-Event observations inside one locked `with self.db` section every five seconds. That is safe only while the cohort is tiny; it is not a bounded steady-state design.

Before volume grows:

- select only unresolved/due work units with a hard per-tick limit;
- keep read/query work outside the shortest possible write transaction where consistency permits;
- append one bounded result batch;
- index unresolved lookup keys used by the scheduler;
- measure p50/p95 tick duration and lock/busy errors; do not raise concurrency to hide a long transaction.

## Missing tests despite the current green targeted set

The current four passing tests do not yet establish:

- request-before / response-after deadline;
- late pair versus queue delay;
- malformed/unsupported registered definition fails closed;
- frozen confirmation window survives class-constant changes/restart;
- exact-address boundary rejection;
- promotional/copied cross-origin mention is not factual confirmation;
- later exact-CA append for no-seed;
- generic EVM multi-chain ambiguity;
- durable local availability versus provider historical time;
- surface-unmapped exclusion from timely same-surface success;
- restart after attempt-before-result and provider-call interruption;
- shared Jupiter fairness/request-rate impact under both lanes;
- full no-pollution assertion across Event→Token relation, Decision, Position, Trade and Live state.

## Deployment verdict

`NO-GO` for deploying the active route-stage patch as a completed full addressability-lag experiment.

`MODIFIED_GO` for keeping it local and continuing targeted implementation/testing, provided the deployed base/route registrations and any naturally created rows are first re-queried. Preserve every existing immutable row. If an already registered definition is semantically wrong, create a corrected version rather than editing or reinterpreting the old one.
