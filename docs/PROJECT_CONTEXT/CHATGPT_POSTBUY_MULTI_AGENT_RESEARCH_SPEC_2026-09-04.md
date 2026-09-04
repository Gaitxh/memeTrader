# Shared Post-Buy Multi-Agent Research Specification

Date: 2026-09-04
Status: `V5 TREATMENT DESIGN / ADVISORY FIRST / HARD EXITS ALWAYS AUTHORITATIVE`

## 1. Objective

After an executable Paper BUY, rapidly investigate whether the token’s identity, narrative, community propagation and manipulation risk justify changing only the **soft holding/runner policy**.

The system must not:

- delay entry waiting for an Agent;
- delay or cancel a mechanical/exact-account exit;
- ask one Agent per strategy arm;
- ask an LLM to calculate price, PNL, pool balance, route, tax or position size;
- turn project self-promotion or a single KOL mention into independent truth;
- backfill a result into the entry decision;
- compare only the positions where the Agent produced a favorable answer.

## 2. One shared case per token/cohort

Create one immutable:

`postbuy_investigation_case(token_id, entry_cohort_id, entry_fill_id, evidence_revision)`

All matching `AGENT_AUGMENTED` allocations reference the same case/result. A new evidence revision may create a new bounded review step, but never updates the prior case.

Use existing source-fact single-flight/canonical-URL/content-revision work to avoid repeated browsing/model calls. Token-specific binding and holding treatment remain per token/cohort.

## 3. Timing tiers

### Tier 0 — deterministic local triage

Target: immediate/current local processing, no LLM.

Assemble:

- exact token/mint/pool/creator identity;
- entry time, amount, surface and current risk state;
- immutable local metadata/social links and provenance roles;
- exact observed posts/events already in the database;
- clone/fanout count and ambiguity;
- creator launch-history lower bound;
- current flow/breadth/concentration/route/account facts;
- previous source-fact results valid for this content revision;
- missing/gap indicators.

This can emit an urgent deterministic contradiction/impersonation flag when exact identifiers conflict, but it never overrides the chain exit state machine.

### Tier 1 — fast bounded dual review

Launch at most two independent semantic roles in parallel after the Paper fill/case is durable.

1. `IDENTITY_NARRATIVE_DIFFUSION`
   - exact official/project identity;
   - original source versus repost/promotion;
   - independent-origin support;
   - narrative intelligibility/relevance;
   - community/KOL propagation already observable;
   - impersonation or unrelated-news risk.

2. `ADVERSARIAL_MANIPULATION`
   - clone/copy/fanout pattern;
   - fake community or coordinated promotion indicators;
   - creator/project contradictions;
   - public scam/rug warnings available now;
   - mismatch between claimed story and observed on-chain behavior;
   - uncertainty/missing evidence.

Use a hard bounded deadline/version. An incomplete/late result is recorded and may be ignored by a short-lived position.

### Tier 2 — optional runner research

Only while a position remains open, is mechanically safe, has positive executable recovery/runner eligibility and Tier 1 suggests useful unresolved upside. This may inspect slower community development or new independent reporting.

Cancel/not-start optional work when the position closes or a hard exit is armed. Preserve the cancellation terminal.

## 4. Agent inputs

Provide only allowlisted, relevant, non-secret facts:

- token/surface public IDs;
- local evidence text/URLs whose collection/use is permitted;
- provenance/observation times and roles;
- deterministic summaries of chain/flow facts;
- exact questions and output schema;
- current cutoff time.

Never provide:

- wallet/private key/signer/broker access;
- config secrets/API keys/session cookies;
- arbitrary project write access;
- unrelated private chats/data;
- future snapshots/outcomes;
- later evidence marked as if available at entry.

Agents have no order/trade tool.

## 5. Structured result contract

```json
{
  "case_id": 1,
  "role": "IDENTITY_NARRATIVE_DIFFUSION",
  "definition_version": "...",
  "input_evidence_revision": "...",
  "cutoff_at": "...",
  "started_at": "...",
  "completed_at": "...",
  "available_at": "...",
  "status": "completed|abstain|insufficient|timeout|error|cancelled",
  "identity": {
    "status": "exact|ambiguous|conflict|unknown",
    "confidence": 0.0,
    "evidence_ids": []
  },
  "independent_origin_count_lower_bound": 0,
  "narrative": {
    "category": [],
    "coherence": "high|medium|low|unknown",
    "propagation_state": "accelerating|active|flat|decaying|unknown",
    "evidence_ids": []
  },
  "risks": {
    "impersonation": "high|medium|low|unknown",
    "clone_fanout": "high|medium|low|unknown",
    "manipulation": "high|medium|low|unknown",
    "contradiction": "present|absent|unknown",
    "urgent_negative": false,
    "evidence_ids": []
  },
  "holding_advice": "accelerate_soft_exit|no_change|runner_candidate|abstain",
  "advice_expiry_at": "...",
  "reason_codes": [],
  "short_rationale": "..."
}
```

All evidence IDs must resolve to facts available no later than `cutoff_at`. Free-form rationale is explanatory only.

## 6. Evidence roles

Preserve distinctions:

- `identity`: links token/project/source but is not support;
- `promotion`: project/KOL promotion with conflict risk;
- `feature`: independent factual/market feature eligible under its version;
- `confirmation`: timely independent support under its version;
- `contradiction/correction`: evidence against a claim;
- `context_only`: useful explanation, not decision truth.

A project metadata link to a celebrity post remains identity/promotion. Reposts sharing the same origin are not independent origins.

## 7. Treatment mapping

### Hard common exits

The following remain deterministic and authoritative for every strategy:

- exact-account emergency;
- terminal dead/no-reentry;
- impossible transfer/current full-size economic failure under its registered rule;
- hard loss/portfolio emergency;
- maximum hold;
- critical execution/data safety rule.

No Agent output overrides these.

### Advisory first phase

Record what the Agent-Augmented policy **would** do, but keep its actual fill path exactly paired with Balanced Dynamic. This measures coverage, timing and counterfactual frequency without contaminating the control.

### Affecting treatment phase

Only after a new preregistered version:

- `urgent_negative` with required evidence quality may arm/accelerate a soft exit;
- `runner_candidate` may widen only the soft trailing/maximum runner allocation within frozen limits;
- positive advice cannot add a new position or average down unless separately researched/registered;
- expired/late/insufficient advice becomes `no_change` for subsequent evaluations;
- conflicting roles follow a deterministic conservative/abstain policy.

The exact mapping and thresholds are frozen before outcome evaluation.

## 8. Latency objective and early results

### 8.1 Natural v1 observer evidence at 2026-09-03T18:35Z

The deployed shared-cohort observer had 21 natural cases after its registration frontier: 21 terminal, 2 `coverage_gap:start_window_missed`, and the other 19/19 completed as `no_context`. Eligible-to-terminal latency across all 21 had median about 35.32 seconds, p95 about 57.79 seconds, minimum 18.54 seconds and one interrupted/outlier path around 262 seconds. No result affected trading.

This result rejects “add more Agents now” as the next optimization. Concurrency is not the demonstrated bottleneck; evidence seeding/token binding is. Two or more Agents receiving the same empty source set would only multiply cost and latency.

Before enabling dual semantic roles, add a deterministic `EvidenceSeedBuilder` that freezes at dispatch:

- exact mint/pool/creator and token program;
- Token metadata URI plus its observed/retrieved revision and provenance;
- allowlisted official website/social links from metadata and pair/profile sources;
- source discovery role/provider and any exact CA/status URL already present locally;
- creator/project launch history lower bound and clone/symbol ambiguity set;
- current narrative search seeds derived without selecting a later winner;
- explicit `no_seed`, `ambiguous_seed`, fetch error and stale/missing terminals.

The builder must single-flight by token/cohort/evidence revision and reuse shared source facts. It must not scrape arbitrary unbounded search space inside the execution loop. A case with no evidence seed should terminate cheaply as `no_seed`, not launch two general-purpose Agents.

Tier-1 Agents remain observer-only until natural cases demonstrate non-empty evidence coverage and results arrive while positions are still economically relevant. A future affecting treatment should be assigned only as a separately registered same-entry paired arm; no favorable-result-only selection.

Record:

- fill-to-case creation;
- case-to-Agent start;
- provider/model duration;
- result available relative to position close and exit state;
- evidence-fetch versus model latency;
- result cost/tokens.

An Agent can emit an append-only early urgent-negative finding before the final report only if the protocol/schema explicitly supports versioned partial results. Otherwise wait for the final bounded result. Never overwrite early/final rows.

## 9. Scheduling and resource control

- max two semantic Agent subprocesses concurrently;
- actual held/Agent-policy positions before generic metadata research;
- exact source/post and deterministic chain-risk work remain separate;
- shared source facts and same content revision reuse one result;
- no Agent if no Agent-Augmented allocation exists, the position already closed, or a hard exit is active;
- optional Tier 2 yields immediately to new held-position Tier 1 work;
- all timeout/error/no-context/cancelled results remain in the denominator.

The concurrency cap protects execution/host resources; it is not an evidence gate. Increase only after measured queue/latency/value shows the model lane is the bottleneck.

## 10. Preventing confirmation bias

- case creation is determined by fill/allocation, not by whether the token later rises;
- both positive and negative/empty results are retained;
- Agents receive a neutral question and no future PNL/ATH;
- exact same Balanced entry is the paired control;
- report treatment effect over all assigned cases, including missing/late/error;
- do not ask agents to justify an existing position or predict a target price;
- rotate/audit role prompts/version rather than silently editing them.

## 11. Learning metrics

Engineering/coverage:

- eligible cases, created, started, completed, timeout/error/cancelled;
- distinct source/evidence coverage;
- latency before first soft decision/position close;
- token/call cost and source-fact reuse.

Quality:

- exact identity conflict/ambiguity rate;
- independent-origin lower bound;
- urgent-negative frequency and later exact adverse outcomes;
- runner-candidate frequency and actual continuation;
- abstention/calibration by evidence quality.

Economic paired outcomes:

- Agent-Augmented minus Balanced net PNL;
- tail/writeoff/drawdown;
- capital time;
- false early-exit opportunity cost;
- positive runner benefit/loss;
- remove-best robustness;
- result by latency/evidence-quality bucket.

Do not condition the primary treatment result on completed/favorable cases only.

## 12. Integration with continuous learning

The LLM does not self-edit prompts/thresholds in production. Changes follow:

1. current cases/results become immutable research data;
2. offline analysis proposes one prompt/schema/treatment change;
3. register new advisory challenger;
4. forward coverage/calibration review;
5. register affecting treatment if warranted;
6. paired Paper maturity;
7. promotion/stop creates a new version.

Model/provider changes are version changes even if the prompt is identical.

## 13. Web presentation

Token/position detail displays:

- case status/timing;
- role results side by side;
- exact evidence references/roles;
- advisory versus affecting treatment;
- whether result arrived before/after exit;
- hard-exit override state;
- cost/token usage;
- no-context/timeout/cancelled terminals.

Home only shows urgent current Agent findings attached to open positions. It does not show generic prose or imply the Agent controls trading.

## 14. Tests

- four Agent-Augmented strategy allocations share one case and at most two role calls;
- Balanced and Agent allocation entries are exact paired;
- late result cannot change a prior holding/exit decision;
- hard exit wins over positive runner advice;
- closed position prevents/cancels optional Tier 2 work;
- identity/promotion alone cannot become independent confirmation;
- source-fact reuse never copies token binding or safety/route eligibility;
- timeout/error/abstain remains in ITT;
- no wallet/secret/order capability reaches Agent input;
- advisory phase cannot mutate position;
- affecting phase requires exact registered version/activation.

## 15. Activation order

1. reuse/normalize existing post-entry case and source-fact infrastructure;
2. implement Tier 0 deterministic evidence package;
3. deploy shared dual-role advisory cases for new v5 Agent allocations;
4. measure coverage/latency/evidence quality and exact paired counterfactual advice;
5. only then design/register an affecting treatment.

Active high-cost general information Agents remain paused until this bounded position-linked path exists. Passive information collection continues because it can make post-buy cases faster and cheaper.
