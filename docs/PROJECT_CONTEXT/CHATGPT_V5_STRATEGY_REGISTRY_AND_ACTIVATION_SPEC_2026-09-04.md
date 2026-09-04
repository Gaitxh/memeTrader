# V5 Strategy Registry, Activation and V4 Supersession Specification

Date: 2026-09-04
Status: `P0 IMPLEMENTATION CONTRACT / NO V4 MUTATION OR BACKFILL`

## 1. Required version transition

The current `chain-meme-trader/v4-paired-vault-rug-truth-20usdc-400bps-zero-fee` registration and all its rows remain immutable.

Stopping **new v4 entry enrollment** must not update its registration. Add a separate append-only supersession/frontier record. Existing v4:

- positions;
- marks;
- exact-account targets/events;
- exit/valuation quote attempts/results;
- SELL fills/writeoffs;
- account snapshots

continue under the v4 policy until terminal.

V5 registration and the v4 entry-stop frontier should be written atomically after code/schema readiness. This prevents double enrollment and coverage gaps.

## 2. Suggested supersession entity

`strategy_entry_frontiers`:

- id;
- stopped_definition_version;
- successor_epoch/version;
- upstream frontier type/id;
- activated_at;
- last eligible observed upstream ID/time;
- reason;
- immutable definition JSON/hash;
- recorded_at.

Unique active stop for the stopped version.

For v4, the upstream boundary must match the source read by `enroll_chain_meme_trader` (currently baseline Jupiter quote result lineage). Codex should verify the exact frontier ID under the same write lock/transaction used to register v5.

V4 enrollment condition becomes:

- source result greater than original activation;
- source result not greater than the immutable stop frontier when one exists;
- existing decision uniqueness unchanged.

Do not infer stop from wall-clock only when the enumerated source uses integer IDs.

## 3. V5 strategy epoch

Suggested epoch:

`chain-meme-trader/v5-independent-policy-kernel-20usdc`

The final version string is Codex-owned, but its definition must include:

- epoch/version/hash;
- activation time and exact upstream frontiers by entry family;
- execution-kernel/cost/MarketFrame/safety/held-monitor versions;
- starting capital and fixed 20 USDC initial notional;
- policy list;
- maturity/promotion definition version;
- no historical backfill;
- Paper mode and Live disabled;
- predecessor v4/frontier linkage.

## 4. Twelve policy IDs

Suggested stable IDs:

| Stage | Policy ID | Entry family | Exit/treatment |
|---:|---|---|---|
| 1 | `launch_recall_fast_escape` | `LAUNCH_RECALL` | `FAST_ESCAPE` |
| 2 | `launch_recall_balanced` | `LAUNCH_RECALL` | `BALANCED_DYNAMIC` |
| 3 | `launch_recall_peak_guard` | `LAUNCH_RECALL` | `PEAK_GUARD` |
| 4 | `launch_recall_agent_augmented` | `LAUNCH_RECALL` | `AGENT_AUGMENTED` |
| 5 | `flow_acceleration_fast_escape` | `FLOW_ACCELERATION` | `FAST_ESCAPE` |
| 6 | `flow_acceleration_balanced` | `FLOW_ACCELERATION` | `BALANCED_DYNAMIC` |
| 7 | `flow_acceleration_peak_guard` | `FLOW_ACCELERATION` | `PEAK_GUARD` |
| 8 | `flow_acceleration_agent_augmented` | `FLOW_ACCELERATION` | `AGENT_AUGMENTED` |
| 9 | `reawakening_fast_escape` | `REAWAKENING` | `FAST_ESCAPE` |
| 10 | `reawakening_balanced` | `REAWAKENING` | `BALANCED_DYNAMIC` |
| 11 | `reawakening_peak_guard` | `REAWAKENING` | `PEAK_GUARD` |
| 12 | `reawakening_agent_augmented` | `REAWAKENING` | `AGENT_AUGMENTED` |

The numeric Stage is display/order only. Policy identity is the immutable string/version, not the number.

## 5. Machine-readable policy definition

Each policy contains:

```json
{
  "policy_id": "launch_recall_fast_escape",
  "display_order": 1,
  "entry_family": {
    "id": "LAUNCH_RECALL",
    "definition_version": "...",
    "activation_frontier": {},
    "readiness": "active|shadow_only|baseline_building|feature_pending|paused"
  },
  "entry_policy_version": "...",
  "risk_bucket_version": "...",
  "selection_policy_version": "...",
  "sizing_policy_version": "fixed-20usdc/v1",
  "exit_policy": {
    "id": "FAST_ESCAPE",
    "definition_version": "...",
    "readiness": "active|advisory|feature_pending"
  },
  "agent_treatment": {
    "definition_version": null,
    "affects": "none",
    "readiness": "not_applicable|advisory|active"
  },
  "execution_profile_version": "...",
  "cost_profile_version": "...",
  "holding_surface_policy_version": "...",
  "paper_role": "executable_candidate|exploration_only|research_only|control",
  "live_eligibility": "false|blocked_pending_evidence|review_candidate",
  "comparison_group": "LAUNCH_RECALL_ENTRY_PAIR",
  "paired_control_policy_id": "launch_recall_balanced",
  "maturity_state": "REGISTERED_EMPTY",
  "no_backfill": true
}
```

Readiness and Paper role are facts, not marketing labels.

## 6. Initial activation states

The registry can contain all twelve policies before all required features are active. Recommended honest initial states:

### LAUNCH_RECALL

- `FAST_ESCAPE`: active after shared execution kernel and its transparent current-data exit rule are implemented;
- `BALANCED_DYNAMIC`: active using a newly frozen v5 translation/reference of existing dynamic logic;
- `PEAK_GUARD`: exact entry allocation may exist as control/advisory, but flow treatment `feature_pending` until strict MarketFrame validation;
- `AGENT_AUGMENTED`: exact entry/control path; Agent treatment advisory/affects none until registered.

### FLOW_ACCELERATION

- entry family `shadow_only/feature_pending` until PumpSwap strict-as-of flow decoder/MarketFrame is naturally validated;
- no executable BUY merely from old provider 5m momentum while the v5 family claims transaction-flow acceleration.

### REAWAKENING

- `baseline_building` first;
- shadow crossings only after valid forward dormant baselines;
- executable Paper only after registered crossing thresholds and shared kernel readiness.

The Web must not count inactive policies as running trades or rank them.

## 7. Common hard execution status

Each policy references, rather than duplicates, common execution facts:

- exact identity/surface;
- no terminal no-reentry;
- deterministic transfer possibility;
- fresh exact amount BUY;
- acquired-quantity SELL preflight;
- route/surface relation and cost completeness;
- queue/total timing;
- capacity/capital selection.

A policy-specific risk feature may reject/select/risk-tier a candidate, but cannot rewrite common plan/result rows.

## 8. Initial exit definitions

### Balanced Dynamic reference

Freeze a v5 definition derived transparently from the current dynamic reference without claiming it is optimal. Preserve current broad concepts:

- hard loss protection;
- trailing activation/drawdown;
- staged profit taking;
- liquidity/activity deterioration;
- maximum hold;
- exact-account emergency override.

Translate triggers toward full-position executable recovery as the authoritative economic state when available. Keep DEX/provider mark as a signal only. Every numeric field is explicit in the definition JSON.

### Fast Escape first challenger

Must be specified before activation and may use only currently available facts:

- tighter maximum loss/recovery protection than Balanced;
- earlier principal-recovery or partial-profit condition using an exact partial quote;
- tighter executable-recovery high-water drawdown;
- shorter maximum hold;
- immediate response to route/liquidity/stall warning;
- same exact-account terminal override.

Do not choose numbers from current v4 winners. Document their economic rationale (turnover cost/tail control) and treat them as a Paper challenger.

### Peak Guard

Before MarketFrame validation, actual exits remain exact Balanced control and only advisory divergence rows are stored. A later affecting policy is a new version/activation.

### Agent Augmented

Before treatment validation, actual exits remain exact Balanced control and Agent advice is `affects=none`. A later affecting policy is a new version/activation.

## 9. Atomic registration procedure

Under the single Store writer/transaction:

1. read current maximum v4 upstream source frontier and relevant discovery/launch/frame frontiers;
2. insert v5 epoch registration and all twelve immutable policy definitions;
3. insert v4 entry-stop frontier linked to v5;
4. insert family activation/readiness rows;
5. commit;
6. Runtime subsequently enrolls v4 only through the stop frontier and v5 only after its family frontier.

On failure, rollback all. Do not leave v4 stopped with no v5 registration, or v5 active while v4 has no stop.

## 10. Concurrency/restart behavior

- unique constraints prevent duplicate registry/frontier;
- Runtime start may call registration idempotently;
- existing v4 due exits run regardless of v5 readiness;
- an in-flight v4 enrollment transaction completes under its original boundary before atomic frontier registration;
- incomplete v5 order intent/attempt follows execution-kernel recovery, not a new registration;
- current policy readiness is derived from append-only activation/status events, not manually edited definition JSON.

## 11. Web truth transition

Before v5 activation:

- v4 page heading: `Historical cumulative evolution epoch`;
- explicitly state entry gates differ across stages;
- do not call it same-entry 12-exit comparison globally.

After v5 activation:

- Cockpit/Strategies defaults to v5 independent policies;
- inactive/advisory policies show exact readiness;
- v4 lives under History and open legacy positions remain visible in a separate `legacy positions still closing` operational panel;
- no combined v4+v5 PNL/rank.

## 12. Acceptance tests

- v4 registration and historical rows byte/row unchanged;
- atomic registration yields both v5 registry and v4 stop frontier or neither;
- no v4 source row after frontier can create a new v4 decision/position;
- source rows at/before frontier retain deterministic prior eligibility;
- existing v4 open position still marks/quotes/closes/writes off;
- v5 never enrolls source rows at/before its family activation frontier;
- all 12 definitions are immutable and machine-readable;
- readiness prevents missing-feature policy from trading;
- same entry family’s active allocations share exact entry lineage;
- Web separates v4 history/v5 policy and never labels inactive policy as active;
- Live remains false/locked.
