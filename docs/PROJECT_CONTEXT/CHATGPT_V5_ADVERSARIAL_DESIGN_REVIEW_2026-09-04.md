# V5 Adversarial Design Review and Required Corrections

Date: 2026-09-04
Reviewer: Lead ChatGPT, adversarial architecture/trading-economics pass
Status: `REQUIRED CORRECTIONS / FOLD INTO GATES A-C / NO COMPETING IMPLEMENTATION BRANCH`

## 1. Purpose

Stress-test the v5 research package before Codex commits to a schema/runtime shape. This review looks for ways the proposed architecture could create false execution truth, false strategy independence, hidden future/order leakage, or an unnecessarily large first release.

The v5 direction remains valid. The corrections below narrow and clarify it.

## 2. Correction A — shared virtual quote is not a shared physical fill

### Failure mode

Four policies inside one entry family each have an independent 20 USDC virtual account allocation. A single fresh 20 USDC quote/preflight may validly serve as the **same-entry market observation** for all four counterfactual Paper policies. It does not mean one 20 USDC physical fill funds 80 USDC of virtual capital, and it does not mean a future 80 USDC physical order can reuse the 20 USDC route/output.

### Required semantics

Separate:

- `ExecutionObservation`: amount/time/route-specific quote/preflight that may be referenced by N exact-identical virtual Paper allocations;
- `VirtualPaperFill`: one simulated 20 USDC fill event per virtual account allocation, all referencing the same observation and using the exact same acquired amount/cost; these fills are analytically paired and never added as physical capital;
- future `PhysicalOrderIntent/Fill`: one exact aggregate amount chosen by PortfolioAllocator, requiring a fresh plan/quote/simulation for that aggregate amount.

The database may deduplicate the provider request/response and derive N allocation fill events, but Web/accounting must make the counterfactual nature explicit. A provider observation is shared; physical notional is not.

### Acceptance

- one 20 USDC observation can support four 20 USDC virtual fills without four provider calls;
- virtual account totals are not presented as an 80 USDC physical position;
- a future aggregate physical amount always receives a new exact-amount plan;
- different amount, deadline, route policy or surface relation cannot share the observation.

## 3. Correction B — same-entry pairing requires identical fill semantics, not merely the same quote ID

All policies in one entry family must freeze identical:

- decision/intent eligibility time;
- exact 20 USDC input;
- conservative acquired raw token amount;
- separately known entry costs;
- plan/observation validity state;
- Paper fill timestamp semantics.

A policy that becomes ready later cannot be retroactively attached to the earlier fill. `PEAK_GUARD` and `AGENT_AUGMENTED` may receive an entry-control allocation only if their definitions/readiness at that entry time explicitly say `control/advisory`. Activating an affecting treatment later creates a new version/frontier; old entries stay control.

## 4. Correction C — no fictitious total transaction order within a Solana slot

### Failure mode

Official log/account notifications provide slot and source delivery order, but a simple logs subscription does not necessarily expose the exact transaction index within a block. Sorting by signature is deterministic but not economic chain order.

### Required clocks/order

Store:

- slot;
- transaction index only when obtained from a source that actually provides/proves it;
- instruction/event index within the decoded transaction;
- block time when available, recognizing second-level/null limitations;
- provider received/local available order;
- `ordering_quality = exact_block_order | slot_partial_order | arrival_order_only`.

For 1/3/5-second online features, use the registered local-availability/receive clock with source-latency and gap indicators unless exact block ordering/time is available. Do not label this as exact exchange event time. For same-slot events without index, aggregate commutative quantities safely and avoid sequence-sensitive features that assume a false order.

If exact same-slot order becomes economically necessary, obtain it through a maintained block/Geyser source and register a new transport/ordering version.

## 5. Correction D — Gate C must not require a natural executable v5 trade before Gate D activates an entry policy

### Failure mode

The Master DAG says Gates A-C create registry and execution kernel, while Gate D activates Launch Recall. Requiring a natural v5 fill in Gate C either activates an unspecified policy early, creates a fake test trade in production, or conflates kernel and strategy release.

### Revised acceptance

Gate C acceptance consists of:

- deterministic targeted tests/fixtures for full decision→observation→virtual Paper fill→position-event semantics;
- deployed empty/idle kernel registrations and idempotent recovery;
- optionally a strict-forward `kernel_observer`/research-only natural opportunity that records plan/no-fill lineage but cannot mutate account/position PNL;
- no production v5 executable fill until Gate D atomically registers/activates the first Launch Recall Fast/Balanced policies.

The first natural executable v5 fill is a Gate D acceptance event. Absence of a natural opportunity is not repaired with a historical winner.

## 6. Correction E — Gates A-C should not create a generic schema bigger than the first lifecycle needs

The research package lists the long-run generic entities. Codex should implement the smallest coherent v5 subset that preserves future compatibility:

- epoch/policy/frontier;
- opportunity/cohort reference;
- strategy decision/allocation;
- execution observation/attempt/result;
- virtual Paper fill/position event/projection;
- exit intent can reuse/bridge current exact exit machinery until Gate E, provided the lineage and future migration boundary are explicit.

Do not refactor every old S1/S2/S3/EVM table or build a universal broker framework in Gates A-C. New v5 rows must be clean; old systems remain immutable.

## 7. Correction F — opaque/unknown surface risk cannot receive exact-pool guarantees

The earlier surface correction is retained:

- exact mint and current two-way amount-specific execution are hard for executable Paper;
- opaque/unknown surface may enter a bounded Paper exploration bucket;
- it has no exact custody/LP/vault safety claim and may lack exact held-account subscriptions;
- route/recovery/data-stall monitoring remains available;
- risk state/UI must show `POOL SAFETY UNKNOWN / LIVE INELIGIBLE`;
- a provider price stall or one no-route cannot produce `DEAD_TERMINAL` without the registered exact evidence predicate.

Do not reuse a different known pool’s watcher/alert for an opaque route token merely because the mint matches.

## 8. Correction G — full-position quote cadence can bias PeakGuard labels

Policies that quote more frequently observe more local executable highs and route gaps. Therefore:

- realized terminal PNL is primary;
- peak-capture/regret is secondary and includes quote coverage/cadence;
- a shared fixed-checkpoint research sampler, bounded by capacity, is preferred for cross-policy peak diagnostics;
- no policy is rewarded merely because it requested more quotes;
- emergency/actual policy quotes remain priority and are not delayed for research symmetry.

## 9. Correction H — virtual accounts are paired experiments, not capital diversification

Twelve strategies on the same four tokens do not diversify risk. Web/learning reports must show:

- raw virtual positions;
- distinct tokens/surfaces/cohorts;
- paired policy allocations;
- independent creator/event/date clusters;
- future physical capital unavailable/locked.

Aggregate virtual PNL across all 12 is not a portfolio claim. Each strategy account may have independent 1,000 USDC Paper cash for experimental comparability; those balances are not additive deployable capital.

## 10. Correction I — no universal exact-pool monitoring means broader Paper needs an explicit emergency fallback

For opaque/noncanonical surfaces without complete exact held accounts, the registered policy must state its degraded monitoring contract:

- high-priority amount-specific full-position route/recovery refresh;
- provider/source freshness and token-level transfer facts;
- shorter maximum hold/tighter capital quota if selected;
- no terminal pool-removal assertion without exact evidence;
- explicit worst-case remaining cost and Live false.

This is not equivalent safety. It is a bounded experiment intended to measure whether opportunity gain compensates for missing structural observability.

## 11. Correction J — do not activate all twelve merely to satisfy the product shape

The registry contains all twelve, but readiness is honest:

- Launch Fast/Balanced become first executable policies at Gate D;
- Launch Peak/Agent stay exact-control/advisory;
- Flow stays shadow/feature pending;
- Reawakening stays baseline building;
- affected Peak/Agent and later entry families each need a new activation event/version.

Strategy count on the homepage means registered definitions; active/filled/ranked counts are separate.

## 12. Revised immediate release boundary

### Gates A-C

1. current premise/authority/r6 verification;
2. atomic v4 entry-stop plus v5 registry/readiness;
3. minimal shared **execution observation + virtual Paper lifecycle** schema/runtime with tests;
4. no active v5 executable entry yet;
5. truthful Web labels and empty readiness states;
6. v4 existing exits uninterrupted;
7. Live locked.

### Gate D

1. preregister exact Launch Recall risk buckets/selection plus Fast/Balanced parameters;
2. activate their frontier;
3. first natural executable v5 opportunity/fill;
4. exact same-entry control allocations for advisory Peak/Agent if ready at that time;
5. validate provider deduplication, virtual accounting, exit capacity and no-backfill.

## 13. Required C2C disposition

Codex should fold these corrections into the single Gates A-C RESULT. A proposed implementation that shares one virtual 20 USDC quote as a future aggregated physical amount, invents same-slot order, forces a natural fill before policy activation, or labels opaque surface safe should return `REVISE`, not deploy.
