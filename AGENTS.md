# memeTrader project rules

## Goal

Run a simple personal-PC bot that discovers real-world/social events and related meme tokens within minutes, ranks the canonical token, and records Shadow/Paper decisions and exits. Keep one Python process, SQLite, JSON configuration, and an optional browser extension unless a proven requirement demands more.

## Execution focus and convergence

- Prioritize changes that improve the requested operating outcome: real source/token coverage, timely candidate quality, Paper execution, and measurable forward learning.
- Before any audit, provenance layer, schema, defensive mechanism, or broad validation, name the currently observed failure it will change. If it does not change an original acceptance criterion or demonstrated runtime bottleneck, do not build it.
- Agent-created reports, ledgers, tests, and review artifacts do not create new product requirements.
- Validate one coherent change with the narrowest relevant check. Do not repeat equivalent reads or tests when code, data, configuration, and hypothesis are unchanged.
- Use at most two similar correction cycles for one failure; then change the causal hypothesis instead of adding reviewers, gates, or validation machinery.
- Full-suite and browser release checks are reserved for a coherent runtime release boundary or an explicit user request, not each local edit.
- When a new request is supplementary, preserve the active product plan and incorporate only the part that materially advances it.
- Treat prior project-chat requirements and suggestions as a governed backlog, not a flat list of simultaneous mandates. Preserve explicitly frozen rules, honor later supersessions/invalidations, and re-evaluate still-open ideas against the current `CURRENT_OBJECTIVE_AND_PLAN.md`, `REQUIREMENT_LEDGER.md`, live forward evidence, and the end-to-end profitability objective. A promising old idea may be revived when evidence supports it, but it must not displace the current P0/P1 merely because it sounds useful or is easier to implement.

## Frozen execution contract

These rules summarize repeated user requirements and remain binding across context compression, new turns, reviewers, and supplementary requests. Change them only when the user explicitly supersedes the specific rule.

- The business purpose is to increase real forward, risk-adjusted meme-token profitability: discover underpriced narrative opportunities earlier, enter and exit them realistically, and learn which signals survive costs and false positives. Profit is never guaranteed, but research, UI, audits, and Agent activity are useful only when they improve or credibly measure that end-to-end outcome.
- At the start of each implementation cycle, identify the highest-impact observed break in `Source/Token discovery → Event↔Token evidence → Decision → Paper execution → fixed-horizon learning`. Implement or remove that break first. Do not substitute an easier UI, documentation, provenance, review, or validation task for the harder core bottleneck.
- UI is a truthful operating surface, not the current optimization target. Improve it when data is missing/misleading or the user cannot operate the system; otherwise prioritize the underlying collectors, mapping, scheduling, Paper execution, and forward evidence.
- Information-first and token-first paths are both required. High-impact fresh information may trigger investigation before price momentum; new-token metadata/social links and on-chain discovery may seed investigation, but identity/promotion never become decision evidence without timely independent support.
- `WAIT` and zero trades are valid outcomes, but sparse Paper activity must be causally explained. Do not loosen evidence/risk gates merely to create trades, and do not call sparsity normal until coverage, scheduling, mapping, quote, and execution blockers have been checked.
- Paper must use only point-in-time available evidence and next-observed/trigger-anchored execution semantics, including configured adverse slippage and fees. Never backfill winners, future prices, later ATH, holder outcomes, or current metadata into an earlier decision.
- Continuous learning requirements remain `CONTINUOUS`; a successful release, test, or short forward window does not complete them. Preserve append-only denominators, failures, empty rounds, missed opportunities, false matches, and fixed-horizon outcomes.
- When a direct platform path is unavailable, use the smallest legal and compliant substitute that preserves provenance and explicitly records the evidence gap. Do not abandon the underlying user objective merely because the originally suggested mechanism is unavailable.
- For generic tooling, data-access, browser, integration, scheduling, routing, or implementation blockers, check official documentation, mature open-source projects, upstream issues/discussions, and credible operating experience before building a custom subsystem. Reuse the smallest maintained solution that fits the current architecture, licensing/platform rules, Windows/single-machine constraints, cost, and failure semantics; do not research dozens of equivalent projects merely for completeness.
- Match Agent/model/reasoning strength to uncertainty and impact. Use ChatGPT high-intelligence collaboration not only for hard blockers, but also when broad research, strategy design, alternative-path discovery, independent critique, or additional domain perspective can materially improve the operating outcome. For broad questions, use the designated Lead ChatGPT first; prefer the highest capable model and highest practical reasoning setting, and verify that the chat was not routed to a lower-tier model. If a chat is routed lower, identifies itself inconsistently with the selected tier, answers implausibly fast for the requested reasoning level, or shows material quality degradation, exclude that response from engineering decisions and reopen the request in a new highest-tier/highest-reasoning chat until a useful answer is obtained. One substantive high-strength Lead review is sufficient by default. Add independent reviewer chats only when the Lead result is materially incomplete, conflicts with current evidence, or the decision has unusually high causal, economic, safety, or release impact; give any added reviewers distinct roles instead of soliciting duplicate generic opinions. Those chats may use the currently designated `@笔记本mcp20260902-2` connection to inspect or operate only the necessary local project files; never send or expose secrets, wallet material, private chats, or unrelated data. When a chat reaches its context limit, open a new chat inside the `GXH coin` project and transfer only a minimal sufficient handoff. ChatGPT supplies research and review; Codex still checks current local evidence, chooses, implements, tests, and owns the result. Production autonomous-search concurrency remains bounded by the configured runtime rule.
- For ongoing ChatGPT↔Codex collaboration, read `docs/PROJECT_CONTEXT/CHATGPT_CODEX_SYNC_STATE.json` first as the fast mutable routing pointer, then open only the referenced items in `docs/PROJECT_CONTEXT/CHATGPT_CODEX_SYNC.md`. One ChatGPT coordinator consolidates independent reviewers; they must not issue competing implementation instructions. At the start/end of a substantial cycle and before deploy/release, Codex verifies referenced items against current evidence and appends one consolidated disposition (`ACK_IMPLEMENTED`, `ACK_DEFERRED`, `REJECT`, or `SUPERSEDED`) with file/method/test evidence, then updates the pointer. Detailed bilateral hypotheses, counterarguments, better implementation ideas and evidence pointers may live in `docs/PROJECT_CONTEXT/COMMON_SPACE/`; each side owns its own notes and immutable outgoing alerts, while realtime messages are short doorbells pointing to those artifacts. Common Space never becomes a second execution plan or authority. Do not interrupt every edit, paste secrets or large logs/diffs, let coordination artifacts create product requirements, or use them to justify parallel edits to files another active turn is changing.
- To wake or contact the designated Lead ChatGPT, read the root `CHATGPT_CONTACT.md` contact card and use its current direct-message target and compact `GXH-C2C/1` envelope. One direct message resumes that ChatGPT conversation; do not start a second Codex writer or paste repository contents. If the target is invalid, use the documented durable-mailbox/rebind path and update the contact target only after validating the new project chat.
- The current GXH ChatGPT project conversations and the designated Codex thread/history are complementary authoritative sources of user intent. Neither may be silently ignored. Resolve apparent conflicts by explicit supersession first, then later/more-specific instruction over older/general wording; if that still does not resolve the conflict, preserve both and record the conflict. Triage every rediscovered user requirement or new ChatGPT/Codex idea by the bottleneck changed, current evidence, expected information/EV gain, cost/risk, and disposition (`PROMOTE_NOW`, `NEXT_CYCLE`, `PRESERVE_CANDIDATE`, `REJECT`, or `SUPERSEDED`). Only a `PROMOTE_NOW` item incorporated into `CURRENT_OBJECTIVE_AND_PLAN.md` or `REQUIREMENT_LEDGER.md` may alter the active scope; otherwise preserve it without interrupting the current P0/P1 cycle.
- A cycle is not complete because its easiest items are complete. Stop only after the named core failure is changed and the narrowest relevant validation succeeds, or after a concrete external blocker is recorded with the next executable path.

## Non-negotiable safety and research rules

- `mode` is `shadow` or `paper`. `live.enabled` remains `false` until a separately reviewed live broker and small-capital chain test exist.
- Historical cases test identity matching, ambiguity, timing, and future-data rejection. Never use later ATH, final winner, exchange listing, current holder counts, or other outcomes as earlier decision features.
- A fact is decision-eligible only when its local `observed_at` and `ingested_at` are not later than the decision time. A `feature` or `confirmation` first observed after the configured freshness window becomes identity-only; stale-only events are deferred until new evidence arrives instead of repeatedly querying DEX/API services.
- Do not commit `config.json`, `data/`, logs, SQLite databases, browser/session material, API keys, wallet material, or private bridge tokens.
- Keep subsequent source/documentation changes local. Do not create Git commits or push to a remote unless the user explicitly reverses the 2026-09-01 instruction that Git publishing is unnecessary.
- Keep every memeTrader database, log, runtime context, Web-console state, test artifact, and temporary Agent workspace under the project on `E:`. Do not create memeTrader storage on the Windows system drive; `load_config()` routes process and child-process temporary storage to `<project>\data\tmp`.
- Free/public sources may fail or rate-limit. Preserve other collectors and record the failure; do not silently treat missing security data as safe.

## Agent-cost routing

- Production memeTrader Agent routing and Codex-development/reviewer Agent routing are separate budgets. For development work, use deterministic local tools for mechanical reads/search/SQL/calculation first; use the cheapest capable model/reasoning tier for narrow routine tasks; escalate root-cause ambiguity, causal/statistical design, architecture, trading economics, experiment design or genuine local-optimum failure to the designated high-intelligence Lead ChatGPT. Do not launch multiple overlapping reviewers merely to increase confidence, and do not use Codex subagents as a substitute for the user's requested high-intelligence ChatGPT review layer.
- Use deterministic local code for polling, parsing, scoring, arithmetic, position sizing, risk limits, and exits.
- Autonomous Agents are allowed for three bounded jobs: global trend scouting, free-source discovery, and high-momentum Token context investigation.
- Keep at most two Agent subprocesses concurrent. Trend/source search uses Spark/low first and Luna/low only as fallback; Token context uses Luna/low, then Terra/medium, with Sol/medium only as the final fallback.
- Enforce daily call budgets, daily token budgets, per-call token reserves, adaptive quiet/surge intervals, a global Token-context cooldown, and a shorter error retry delay. A manual `--force` may bypass time due checks but never daily budgets.
- The separate semantic tie-breaker remains disabled by default; uncertain canonical rankings return `WAIT` instead of forcing a winner.
- Agents never receive wallet, broker, private key, project-write access, or permission to bypass local risk rules.

## Required checks for an in-scope change

Run the closest targeted test, then the full suite before a release or push:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q src tests
.\.venv\Scripts\python.exe -m memetrader doctor --config config.json --online
```

For resident-operation changes, verify the single scheduled task, port `8765`, `/health`, `IgnoreNew` behavior, and one forced child-process restart.

## Current device deployment

- Working folder: `E:\memeTrader`
- Scheduled task: `memeTrader Paper Bot` (interactive user, at logon, `IgnoreNew`, battery-safe)
- Runtime database: always resolve `database` from ignored `config.json`; current device path is `data\memetrader_forward_20260830_r6.sqlite3`. Earlier `r5` contains rejected false-positive Paper evidence from promotional listicles and must not be merged into performance statistics.
- Browser bridge: loopback only on `127.0.0.1:8765`
- Manual step: load `browser-extension` as an unpacked Chrome/Edge extension and copy the local `bridge.token` from ignored `config.json` into its options.
