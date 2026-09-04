# C2C-20260903-STRATEGY-POLICY-ARCH-UI-COMMS-003

PRIORITY: P0 / USER-EXPLICIT ARCHITECTURE CORRECTION
TYPE: DESIGN_CORRECTION / INCREMENTAL_IMPLEMENTATION_DIRECTIVE
OWNER: Codex
FACT_CUTOFF_UTC: 2026-09-03T06:58:00Z
BLOCKS_LIVE: true
BLOCKS_NEXT_STRATEGY-3-TREATMENT_RELEASE: true
BLOCKS_CURRENT_HEALTHY_RUNTIME: false

## 1. Latest user correction: strategy family != buy/sell method

The product model is exactly three strategy families:

1. **Strategy 1 — News/Information + Token**: news, public figures/KOLs, social/community/hotspot and Token/market/on-chain evidence jointly determine opportunity state and entry.
2. **Strategy 2 — Token-only**: Token/launch/pool/on-chain/market-microstructure evidence determines opportunity state and entry; no narrative evidence is required.
3. **Strategy 3 — Token-first, then News/Hotspot judgement**: enter from Token-first evidence, then immediately and continuously investigate news/hotspot/public-figure/community/narrative/creator context; that post-entry information may eventually change sizing, hold, partial exits or runner policy after forward validation.

Every strategy family has its own **buy-policy and sell-policy variants**. Position size, tranche count, sell fractions, stop/trailing/time exits, runner fraction and max hold are policies inside a strategy, not separate top-level strategies. The current UI/backend description “three accounts, two entry logics” is therefore incomplete and should be superseded by **three strategy families with multiple versioned policy arms**.

The current exact Strategy-2/Strategy-3 pairing remains useful only as a causal experiment that estimates incremental post-entry information value. It must not become a permanent product definition that prevents Strategy 3 from later owning validated sizing/exit rules.

## 2. Required domain separation

Do not create 3 strategies × N exits × chains as unrelated accounts. Introduce a minimal machine-readable separation:

- `strategy_family_version`
- `signal_policy_version`
- `entry_policy_version`
- `sizing_policy_version`
- `exit_policy_version`
- `cost_model_version`
- `chain_execution_profile_version`
- `activation_at / activation_source_id`
- `research_state`
- `decision_eligible / affects`

A concrete Paper arm is a tuple of those versions. Old ledgers remain immutable. First implementation can map current behavior without changing trading; do not migrate/rewrite historical rows.

### Initial arm map

- S1 baseline: information+Token signal / current canonical+safety gate / current fixed $20 fair sizing / current deterministic exit / chain-aware cost profile.
- S2 fixed-horizon arm: token-only momentum baseline / amount-specific entry / fixed 15-60-240 exit.
- S2 dynamic-exit arm: same S2 entry / hard-stop, trailing, inactivity, staged TP, max-hold.
- S3 causal-control arm: exact S2 entry and exact matching control exit, post-entry information collected but no treatment effect.
- S3 treatment arm (future only): same causal-control admission; post-entry event-driven evidence may alter a preregistered subset of size/hold/exit fields.

The dynamic exit library should be reusable by any strategy family after a distinct registered arm; it is not inherently “Strategy 2 only”.

## 3. Self-regulation boundary

“Self-adjusting” must mean versioned forward policy learning, not per-trade self-editing.

Required lifecycle:

`COLLECTING -> MATURE_DESCRIPTIVE -> POLICY_CANDIDATE -> PREREGISTERED_PAPER_ARM -> FORWARD_COMPARISON -> TEMPORAL_HOLDOUT_PASS -> PROMOTABLE / REJECTED`

Candidate policy dimensions:

- entry notional / risk budget / max concurrent exposure;
- single vs staged entry;
- stop/trailing/time exit;
- take-profit thresholds and sell fractions;
- runner fraction/max duration;
- chain/surface/regime-specific cost and capacity;
- post-entry narrative treatment for S3.

Use constrained optimization over net executable PNL, drawdown, catastrophic-loss rate, no-route rate and capital lock. Do not optimize mean return or ATH. Keep an exploration arm. No automatic promotion from retrospective data or one profitable trade.

## 4. Open-source/official reuse shortlist verified 2026-09-03

Do not replace memeTrader wholesale. Reuse patterns/components selectively:

- **Hummingbot** (Apache-2.0, active): borrow Controller/Executor separation and reusable strategy/execution components; do not import its full connector/runtime stack unless a concrete need appears.
- **NautilusTrader** (LGPL-3.0, active): borrow deterministic event-sourced order/portfolio semantics and backtest/live parity concepts; license boundary must be reviewed before code reuse.
- **River** (BSD-3-Clause): candidate for incremental models, calibration and drift-aware statistics after labels mature; no direct online production threshold edits.
- **Optuna** (MIT): temporal train/validation parameter search for sizing/exit policy candidates; never search against sealed holdout/test.
- **MLflow** (Apache-2.0): possible policy/model experiment registry if the current JSON/SQLite registry becomes insufficient; not a current dependency requirement.
- **Foundry/Anvil** (Apache-2.0): EVM fork/simulation candidate for BSC/Robinhood transaction, allowance, revert and gas semantics.
- **RSSHub** (AGPL-3.0), **Huginn** (MIT), **Trafilatura** (Apache-2.0): source discovery/extraction candidates; platform terms, provenance and independent-evidence rules still apply.
- **BERTopic** (MIT): offline/local narrative-cluster exploration only; not an oracle or direct trading score.
- **Apache ECharts** (Apache-2.0), **uPlot** (MIT), **Tabulator** (MIT): UI candidates. Prefer uPlot for dense real-time equity/latency series, ECharts for richer research plots, Tabulator only where existing tables truly need sorting/filtering/virtualization. Avoid a framework rewrite merely for appearance.

Repository activity/license was checked from official GitHub metadata. Before adoption, Codex must inspect the exact module license/API and choose the smallest maintained component.

## 5. UI information architecture

Current UI mixes operating truth, strategy results and research diagnostics. Redesign by information priority, not colors.

### Level 1 — Operations header

- Runtime/collector/quote/Agent heartbeat;
- Live locked;
- active strategy-policy versions;
- data freshness and material blockers.

### Level 2 — Strategy workspace

Exactly three tabs: S1, S2, S3. Each tab has:

- common KPI contract: cash, realized PNL, executable unrealized PNL, unknown/unpriced exposure, drawdown, wins/losses, capital lock;
- chain filter/breakdown: ALL / SOL / BSC / ROBINHOOD (retain Base as research/backlog unless later explicitly dropped);
- active entry/sizing/exit/cost policy versions;
- positions and fills with chain badge, execution-quality badge and fee components;
- policy-arm comparison inside the strategy, not as another top-level account.

### Level 3 — Opportunity and evidence

Narrative/Event-first, Token-first and Token-first→context timelines, exact CA/canonical ambiguity, safety and route state.

### Level 4 — Research lab

Liquidity survival, creator history, holder/first buyers, source/KOL utility, policy challenger and missing/error denominators. Collapsed by default and never mixed into account PNL.

Truth badges must distinguish `EXECUTABLE`, `MODELED`, `INDICATIVE`, `UNKNOWN`, `NO_ROUTE`, `WRITTEN_OFF`.

## 6. Chain scope and cost semantics

Immediate production/research focus is Solana, BSC and Robinhood as explicitly restated by the user. Preserve the existing Base adapter/research records; do not let Base block this release, and do not delete it absent explicit user cancellation.

Keep three strategy families, then break results down by chain. Do not create twelve headline accounts.

- **Solana**: Jupiter amount-specific minimum output; SOL network/priority/signature/rent components when transaction build/simulation evidence is available; Pump/venue fee semantics by market surface.
- **BSC**: aggregator/direct route amount, BNB gas, allowance, token tax, honeypot/max-sell/blacklist/transfer behavior, exact sellability. Foundry/Anvil fork simulation is a candidate supplement, not a substitute for forward route evidence.
- **Robinhood Chain**: chain 4663, ETH gas, independent execution profile, official Stock Token/RWA address exclusion before Meme admission, EVM security coverage and amount-specific route. Never inherit Base/BSC cost values blindly.

The current $20 + 4% adverse execution + $0.40/fill remains a clearly labeled frozen stress arm only. It is not a universal real fee model.

## 7. Communication finding and immediate fix

The official-tunnel MCP can open and edit `E:\memeTrader`, open the Codex project mirror, run commands/tests and inspect processes under the logged-in Windows user. It is not itself a Codex conversation controller.

Current CLI exposes experimental `codex remote-control` and authenticated app-server websocket support, but do not activate it against the active writer without an isolated read-only proof. `codex resume <thread> <prompt>` can start/resume a CLI session but may create a competing writer; it is forbidden while the Desktop thread is active.

Concrete current bug: `scripts/codex_project_context_guard.py` selects `open_groups[0]` whenever `attention_required=true`. The first group in the current pointer is already ACKed, while the material latest group is later. Therefore the hook can inject a stale alert and miss the new one.

### Immediate safe implementation task COMMS-1

At the next stable checkpoint, change the guard to select the highest-priority unresolved group, preferring:

1. `blocks_release=true`;
2. status containing `ATTENTION_REQUIRED`, `OPEN`, `BLOCKED`, or equivalent unresolved state;
3. newest group/message when tied.

Ignore ACKED/RESOLVED/SUPERSEDED groups. Keep only one compact alert in injected context. Add a narrow deterministic test or invoke the hook with a representative payload. Do not start app-server remote control in this change.

Future COMMS-2, separately reviewed: a loopback-only authenticated app-server “doorbell” that can notify the active Codex UI of a new artifact without shell or write authority. It must remain one-writer, message-ID deduplicated and capability-token protected. Until proven, the durable pointer/hook is authoritative.

Codex→Lead ChatGPT should continue using the existing exact-thread direct message path where available, with durable mailbox fallback. Lead→Codex uses immutable artifact + pointer; direct injection is optional, not required for correctness.

## 8. Ordered implementation handoff

Do not interrupt an in-flight coherent test/release task. At its stable checkpoint:

1. **COMMS-1**: fix stale `open_groups[0]` selection so subsequent handoffs are reliably seen.
2. Resolve any current source/startup mismatch and current-version quote dispatch blocker already identified by prior alert.
3. **STRATEGY-MODEL-1**: add a minimal machine-readable strategy-family/policy-arm contract to backend output and authoritative plan; map existing arms without changing fills.
4. **S3-CONTROL-1**: correct the next S3 causal-control version so information treatment is the only planned difference; preserve old versions.
5. **UI-IA-1**: implement the new four-level information architecture incrementally, starting with Strategy tabs + policy versions + chain filter + truth badges; no full framework rewrite.
6. **CHAIN-EXEC-1**: Solana/BSC/Robinhood chain execution profiles and fee components; quote-only EVM remains non-PNL until simulation/sellability/cost completeness.
7. **POLICY-LEARNING-1**: expose research-state/promotion pipeline before allowing any adaptive amount or sell-fraction activation.

ACK with the exact files/methods/tests chosen for COMMS-1 and STRATEGY-MODEL-1. Do not claim the entire long-running program complete after those two increments.
