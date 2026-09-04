# Lead ChatGPT current handoff — 2026-09-03

Status: `AUTHORITATIVE CONTINUITY DELTA / READ BEFORE RESUMING`
Purpose: let a new GXH coin ChatGPT continue immediately without re-explaining old history. Do not treat this as a substitute for current code/SQLite/sync facts.

## User communication preference

- Do not repeatedly restate the whole project history, strategy definitions, safety rules or prior conclusions unless the user explicitly asks for a recap.
- On a new chat, restore context from E:\memeTrader, verify current facts, then continue the latest executable work directly.
- A one-word user prompt such as `继续` inside the GXH coin project should be sufficient to resume from this handoff + sync pointer.
- Lead ChatGPT has an active obligation to discover material strategy, news/source-coverage, execution and efficiency problems through bounded read-only inspection; do not rely solely on Codex to raise issues.
- Avoid unnecessary defensive work, duplicate audits/reviews, reassurance tests or reviewer loops. Investigate only when tied to a concrete bottleneck, material causal/economic risk or forward evidence change.

## Latest strategic supersession — read before the older model below

As of `2026-09-03T11:58:26Z`, finite resources are concentrated on one active development and Paper-promotion path: **Solana canonical Pump.fun → PumpSwap, pure on-chain momentum, RPC-verified custody/LP burn, exact-size Jupiter BUY→SELL preflight and deterministic dynamic exit**. The older three-family and multi-chain sections below remain the preserved product/backlog model, but they no longer authorize concurrent active work during this focus cycle.

- Pause high-cost Trend/Source/Token-Context/Verifier/WATCH/post-entry narrative Agent dispatch, new S1/S3 Paper promotion, EVM work and additional Solana venue expansion at a forward focus frontier.
- Preserve cheap passive RSS/browser/on-chain collection, immutable S1/S3/EVM history and Research Lab optionality.
- PumpSwap RPC custody v2 is the primary venue base. Preserve Raydium CPMM v3 as research-only; do not continue AMM-v4/CLMM/Orca/Meteora work now.
- A confirmed on-chain liquidity withdrawal/rug gets at most one immediate full-remaining-size SELL attempt, then permanent terminal write-off/no-rearm/no-automatic-reentry for that mint/pool/policy lineage. One no-route, provider error or DexScreener zero alone is not a confirmed rug.
- Before any new primary BUY, fix the current positive-penny preflight weakness: exact-size immediate net recovery must meet a preregistered full round-trip cost floor, not merely be greater than zero.
- Current momentum threshold and dynamic TP/stop parameters stay frozen; fixed 15/60/240 remains the comparator. No capital/venue/chain expansion before the maturity and winner-removal gates.
- Implement the read-only 1-second terminal cockpit before broad Web redesign.

Authority: `CHATGPT_ONCHAIN_FIRST_STRATEGIC_CONVERGENCE_2026-09-03.md`, `COMMON_SPACE/ALERTS/CHATGPT_TO_CODEX/C2C-20260903-115826-CHATGPT-ONCHAIN-FIRST-PRIMARY-P0.md`, and the fast sync pointer.

## Latest product model

There are exactly three strategy families:

1. `S1 information_plus_token`: news/hotspots/public figures/KOL/community/narrative + Token/onchain/market evidence jointly determine entry.
2. `S2 token_only`: Token/onchain/market/safety/execution evidence determines entry without requiring narrative.
3. `S3 token_then_information`: precisely mirrors each eligible Strategy-2 Token/onchain BUY, then gathers news/hotspot/person/community/narrative/creator evidence after entry to test whether information improves dynamic holding and exit decisions.

Each strategy family can own multiple independently versioned policy arms: entry timing, position sizing, staged entry, hard stop, trailing, take-profit thresholds, sell fractions, runner fraction, max hold, liquidity/no-route handling and chain-specific execution/cost profiles. Every family needs both a fixed-horizon comparison baseline and one or more dynamic-exit arms; fixed horizon is not the strategy itself. Exit methods are policy arms, not additional top-level strategies.

The exact-S2-clone / post-entry-information lane remains the product-facing Strategy 3 under the user's later, more specific instruction. Current Store v3 has corrected its baseline to the fixed S2 baseline. The separate strict-forward `TOKEN_TRIGGER -> WATCHING -> INFO_PENDING -> CONFIRMED | NEGATIVE | EXPIRED` lane remains an observer-only research challenger with `entry_enabled=false / decision_eligible=false / affects=none`; it must not create a fourth account or replace Strategy 3 without a future explicit supersession.

## Learning / optimization model

The system is collecting substantial strict-forward evidence, but automatic strategy optimization is not yet mature. Do not claim online self-optimization is active. Use versioned staged promotion:

`COLLECTING -> MATURE_DESCRIPTIVE -> POLICY_CANDIDATE -> PREREGISTERED_PAPER_ARM -> FORWARD_COMPARISON -> TEMPORAL_HOLDOUT_PASS -> PROMOTABLE | REJECTED`

Optimize candidate sizing/exit rules only from mature temporal evidence and executable net outcomes, with drawdown, catastrophic loss, no-route and capital lock constraints. No per-trade self-editing and no future/ATH labels.

## Chain scope

Immediate implementation focus is Solana, BSC and Robinhood Chain. Preserve Base research/history and adapters; Base should not block the immediate three-chain work and should not be deleted unless the user explicitly cancels it.

Every Token/position/trade/PNL row must carry chain identity and execution-quality truth. Use dynamic observed costs when available; otherwise a frozen fallback must be explicitly `MODELED`, never presented as real chain fees.

- Solana: amount-specific Jupiter BUY/SELL minimum output; route/price impact; reliable signature/priority/rent fee evidence when available; Pump/PumpSwap surface-aware fees.
- BSC: amount-specific route, BNB gas, allowance, token tax, honeypot/max-sell/blacklist/fee-on-transfer and actual sellability. Prefer mature aggregator route; use Foundry/Anvil fork simulation as a research validator.
- Robinhood Chain: chain id 4663, ETH gas, independent execution profile, EVM safety support and deterministic official Stock Token/RWA exact-address exclusion before Meme admission.

The current `$20 + 4% adverse execution each side + $0.40/fill` fair experiment is a frozen conservative stress arm, not a universal real fee model.

## UI direction

Incrementally reorganize rather than rewrite the frontend framework.

1. Operations header: runtime/collectors/Agent/route/quote/freshness/blockers/Paper/Live lock.
2. Three strategy tabs S1/S2/S3. Each shows cash, realized PNL, executable unrealized PNL, unknown/unpriced exposure, drawdown, wins/losses, capital lock, active policy versions and policy-arm comparison.
3. Chain breakdown/filter inside each strategy: ALL / SOL / BSC / ROBINHOOD; Base retained in research until promoted.
4. Opportunity/evidence timeline separated from account results.
5. Research Lab collapsed by default: liquidity survival, creator history, first buyers/holders, source/KOL utility, Agent admission, missing/error denominators and policy-promotion state.
6. Truth badges: EXECUTABLE / MODELED / INDICATIVE / UNKNOWN / NO_ROUTE / WRITTEN_OFF.

## Current implementation/release issues to verify first

Read `CHATGPT_CODEX_SYNC_STATE.json` and its newest unresolved release-blocking artifacts before acting. At this handoff the important outstanding items are:

- communication guard stale-alert bug: `scripts/codex_project_context_guard.py` must not blindly select `open_groups[0]`; select the highest-priority unresolved item and ignore ACKED/RESOLVED/SUPERSEDED entries;
- current checkout/runtime source consistency must be verified before any controlled restart;
- current 20-USDC Solana onchain cohorts existed while Jupiter v2 had no attempts/results in the Lead diagnostic window; diagnose current-version quote dispatch before interpreting S2/S3 zero trades;
- correct the next S3 control version before collecting a new clean paired treatment cohort;
- EVM Quoter-only results remain research/modeled until transaction/sellability/full-cost semantics are complete.

Current facts may have advanced after this file was written. Code, SQLite, tests, running processes and the fast sync pointer override stale counts here.

## Open-source / external implementation direction already researched

Selective reuse only; do not replace memeTrader wholesale:

- Hummingbot: Controller/Executor separation pattern.
- NautilusTrader: deterministic event/order/portfolio semantics reference.
- Optuna: temporal/offline candidate policy search, not sealed holdout optimization.
- River/ADWIN: later drift monitoring/review trigger, not automatic production threshold mutation.
- Foundry/Anvil: EVM fork transaction/sellability/gas validation.
- 0x: mature EVM amount-specific routing candidate for supported chains when configured.
- Robinhood official Stock Token API: exact-address asset exclusion source.
- Trafilatura/RSSHub/Huginn/BERTopic: optional source/narrative research components, subject to licensing/platform/provenance rules.
- ECharts/uPlot/Tabulator: optional UI components only if a concrete chart/table bottleneck justifies adoption.

Detailed rationale: `CHATGPT_STRATEGY_POLICY_ARCH_RESEARCH_2026-09-03.md`.
Implementation-facing delta: `COMMON_SPACE/ALERTS/CHATGPT_TO_CODEX/C2C-20260903-STRATEGY-POLICY-ARCH-UI-COMMS-003.md` and `C2C-20260903-MULTICHAIN-STRATEGY3-LEARNING-GATE-002.md`.

## Collaboration / continuity

- Codex execution thread remains `01a0514b-bbb5-7400-baf9-d9feb4dc603d` and remains the sole business-code writer.
- Lead ChatGPT researches/reviews/coordin­ates; do not create a second writer just to deliver a message.
- Durable detail lives on E:. Direct messages are short doorbells when available.
- `CHATGPT_CODEX_SYNC_STATE.json` is the current routing pointer; current code/SQLite/tests override stale snapshot text.
- If this Lead chat reaches context limits, a new GXH coin chat reads the rollover boot set, this handoff and sync pointer, then continues without asking the user to repeat project history.

## Immediate continuation behavior for a new ChatGPT chat

When the user says `继续`:

1. Read `AGENTS.md`, this file, `CHATGPT_CODEX_SYNC_STATE.json`, the newest unresolved referenced artifact(s), and only the necessary current code/SQLite facts.
2. Do not give a long recap unless requested.
3. Continue research/analysis or implementation handoff from the highest-impact currently unresolved profitability bottleneck.
4. Persist material new conclusions to E: before context loss.
