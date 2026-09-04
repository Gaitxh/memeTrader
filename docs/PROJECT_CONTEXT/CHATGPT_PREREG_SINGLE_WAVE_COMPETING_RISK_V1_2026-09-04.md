# GXH Single-Wave / Competing-Risk Exit Study — Forward Preregistration V1

- Owner: ChatGPT Lead research specification; Codex sole implementation/deployment writer
- Registration status: DESIGN, not active until Codex freezes an activation frontier
- Date: 2026-09-04 Asia/Tokyo
- Live authority: none; Paper/observer only
- Depends on: common MarketFrame, all-position RiskKernel, unique cohort identity, common executable sampling

## 1. Decision question

For a young exact Token/pool cohort that has already produced a meaningful executable run-up and then a persistent drawdown, which occurs first under strictly forward observation?

1. Reclaim or exceed the prior full-position executable-equity high; or
2. Hit a common hard-loss floor, RED/DEAD, no-route terminal or other irreversible economic breakdown.

The study estimates the value of:

- holding through the drawdown;
- exiting at the event;
- using a high-water trailing exit;
- exiting and later opening a new REAWAKENING cohort.

It does not attempt to identify a final historical ATH.

## 2. Immutable activation and cohort identity

Codex registers:

- `study_version`
- `registered_at`
- `activation_market_frame_id`
- `activation_source_buy_fill_id`
- frozen grid and outcome contract hash

No frame/event before the activation frontier may be admitted.

Independent cohort key:

`chain + exact token/mint + exact pool/surface + source entry cohort + reawakening_generation`

Strategy account, Stage number, copied position and UI card are not independent cohorts.

## 3. Eligibility

A cohort is eligible only when, as-of the event:

- exact position/surface identity is resolved;
- full remaining raw amount is known;
- at least one valid full-amount executable observation exists after entry;
- executable observation coverage and held-account feed state are explicit;
- the cohort is not already DEAD;
- no earlier event from this study exists for the same generation.

Coverage gaps are retained as explicit terminal/incomplete states; they are not silently excluded after outcomes are seen.

## 4. Shared executable-equity series

For remaining amount `q_t` and realized cash `C_t`:

- `X_t(q_t)` = exact full-amount minimum executable recovery;
- `E_t = C_t + X_t(q_t)`;
- `H_t = max(E_s, s <= t)` from the common immutable valuation stream;
- `D_t = 1 - E_t/H_t`.

Every arm consumes the same valuation IDs and coverage state. Quote frequency/priority may not differ by treatment. Held-account frames may be faster than aggregator valuations, but any quote-triggered outcome is tied to the first common valid valuation after the trigger.

## 5. Frozen descriptive grid

The initial grid is deliberately coarse and descriptive. It is not a combinatorial optimizer.

Prior as-of executable run-up cells:

- `R25`: >= +25%
- `R40`: >= +40%
- `R75`: >= +75%
- `R150`: >= +150%

Drawdown cells from executable high:

- `D10`, `D15`, `D20`, `D30`

Persistence cells:

- `P0`: first valid observation
- `P3S`: persists/corroborates for >=3 seconds
- `P10S`: >=10 seconds
- `P30S`: >=30 seconds

Observation horizons:

- 15 seconds
- 60 seconds
- 5 minutes
- 15 minutes
- 60 minutes
- 240 minutes

Operational policy versions later choose only a small frozen subset. Existing natural cases are fixtures, never admitted as post-registration study outcomes.

## 6. First qualifying event

For each cohort/generation, the study freezes the earliest frame at which a run-up/drawdown/persistence cell becomes satisfied. It stores:

- event/frame/valuation IDs and as-of time;
- full executable equity, high and drawdown;
- exact remaining amount and realized cash;
- reserve/flow/risk state;
- observation freshness/gap;
- market age, venue/program and migration phase;
- unique-flow/concentration fields available as-of;
- source/narrative evidence available as-of.

Overlapping later drawdowns are not separately counted. A new event requires a separately registered REAWAKENING generation.

## 7. Competing outcomes

Primary outcomes are mutually ordered by first occurrence after the event.

### 7.1 Recovery outcomes

- `REHIT_H0`: common executable equity >= frozen pre-event high
- `NEW_HIGH_10`: >= 1.10 times frozen pre-event high

### 7.2 Breakdown outcomes

- `COMMON_HARD_STOP`: common safety hard-stop event
- `RED`: versioned RiskKernel RED
- `DEAD`: exact terminal
- `NO_ROUTE_TERMINAL`: explicit frozen retry/writeoff terminal
- `RECOVERY_FLOOR`: executable equity below a frozen common fraction of entry cost, when not already classified above

### 7.3 Censoring

- horizon reached with neither competing event;
- observation ended/restart without sufficient recovery coverage;
- surface identity became ambiguous;
- administrative experiment intervention.

Censoring type/time is stored. It is never converted to “did not recover.”

## 8. Secondary path outcomes

- maximum executable recovery after event;
- minimum executable recovery after event;
- time to first rebound, high rehit, RED/DEAD;
- number and spacing of failed high attempts;
- rebound amplitude and half-life;
- quote/base reserve path;
- full-size impact path;
- route availability and provider disagreement;
- hypothetical exit Fill at next common quote after each trigger;
- exit-then-reentry economics for a separately frozen reawakening rule.

## 9. Economic counterfactuals

At each qualifying cell, calculate without creating fake live orders:

A. `HOLD_COMMON_SAFETY`
- continue under shared hard stop/RED/DEAD/max-hold.

B. `EXIT_NOW`
- create a counterfactual at first common next-quote minimum output.

C. `ARMED_EXEC_DECAY`
- frozen arming/drawdown treatment under the common safety envelope.

D. `PRINCIPAL_THEN_TRAIL`
- only after separately registered; include realized cash in executable equity.

E. `EXIT_REAWAKEN`
- exit, then allow a separately qualified new cohort; charge all exit/reentry costs and missed-gap opportunity.

Every result includes execution level and does not treat quote simulation as confirmed execution.

## 10. Primary analyses

1. Cumulative incidence of high rehit/new high versus breakdown by horizon.
2. Net executable PNL difference of each policy versus common control on terminal-comparable unique cohorts.
3. Conditional results by run-up/drawdown/persistence cell.
4. Conditional results by reserve/recovery/flow regime.
5. Tail, no-route and writeoff incidence.
6. Capital-hour return and time-to-release capital.
7. Remove-best-1/remove-best-3 and Top1/Top3 contribution.

When sample size supports it, use competing-risk/survival estimates with right-censoring. Before that, report exact denominators and outcome counts rather than unstable model coefficients.

## 11. Dependence and robustness

- block/cluster by exact token family, deployer/creator cluster and clone/fanout group where known;
- do not bootstrap 12 Stage accounts as independent;
- report venue and age strata;
- separate periods with degraded quote/feed coverage;
- preserve all failed/missing cases in denominator accounting;
- freeze a temporal confirmation block before selecting a deployable threshold.

## 12. Sequential decision policy

The purpose is fast profitable learning, not endless shadowing.

- As soon as the first coherent forward block has enough unique terminal-comparable cohorts to expose direction and tail, one bounded challenger may be promoted to Paper champion/challenger status.
- Promotion is not based on a nominal p-value alone. It requires positive unique executable economics, no dependence on one winner, no worse catastrophic tail, and sound coverage/execution lineage.
- A promoted treatment retains a concurrent control allocation/counterfactual and a kill/retirement frontier.
- Larger capital or Live authority requires a later temporal block and execution-level advancement.

Exact numerical maturity gates must be registered by Codex with current cohort arrival rate; they may not be chosen after seeing favorable outcomes.

## 13. Minimum schema contract

### `single_wave_study_registrations`

- version, registered_at, activation IDs, contract JSON/hash, status

### `single_wave_events`

- immutable cohort/generation/event IDs
- run-up/drawdown/persistence cell
- source frame/valuation IDs
- as-of market/risk/coverage snapshot

### `single_wave_outcomes`

- append-only outcome observations
- first competing terminal
- horizon/censor status
- source frame/quote/fill lineage

### `single_wave_policy_counterfactuals`

- policy version
- source event
- intents/quotes/fills or explicit unresolved state
- costs, realized/recoverable equity, execution level

No table writes Decision/Position/Trade for observer-only study counterfactuals. Any promoted Paper arm uses the standard order kernel.

## 14. Test/acceptance cases

1. No event before activation frontier.
2. One cohort/generation produces at most one first event.
3. A later wave requires new REAWAKENING generation.
4. Future ATH cannot change event high/drawdown.
5. Quote sampling is common across arms.
6. Partial exit accounting includes realized cash in total executable equity.
7. Control and treatment share a hard-stop/RED/DEAD event ID.
8. Observation loss produces censoring, not non-recovery.
9. Copied Stage accounts yield one independent denominator unit.
10. Restart and duplicate frames are idempotent.
11. Same immutable frames replay to the same event/outcome.
12. Administrative v1 cleanup remains an intervention, never a strategy outcome.

## 15. Deliverables

- one future-only registration artifact;
- implementation methods and schema migration;
- targeted deterministic tests;
- read-only cohort/outcome report;
- first natural event/outcome notification;
- no threshold promotion until the registered common RiskKernel/valuation stream is active.
