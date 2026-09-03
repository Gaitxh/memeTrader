# ChatGPT ↔ Codex collaboration protocol · 2026-09-02

Status: `PROPOSED_FOR_CODEX_ACKNOWLEDGEMENT`

## Objective

Optimize the system for **genuine forward, executable, cost-adjusted, risk-adjusted expected value**. Trade count, raw return, backfilled winner discovery and dashboard activity are not objectives. No profitability claim is valid until supported by natural forward Paper evidence under frozen rules.

## Authority order

1. Current bytes in the real repository and read-only facts from the designated forward SQLite database.
2. Current running-process, scheduled-task, bridge and Live-lock facts.
3. Current preregistrations and immutable ledgers.
4. Current continuity/requirement/project-context files.
5. Review notes and chat/thread messages.
6. Historical handoff archives, used only for long-term context.

A lower layer never overrides contradictory current evidence. Every deployment decision re-queries the live boundary immediately before restart.

## Default topology

### Persistent pair

- **Lead ChatGPT:** global objective keeper, causal/statistical and trading-economics challenger, architecture reviewer, runtime/SQLite verifier and cross-thread coordinator. Read-only on active implementation files unless explicitly taking ownership at a clean boundary.
- **Codex:** sole writer/integrator in the active checkout; implements, tests, performs controlled restart, updates authoritative context and records evidence.

### Bounded independent review at major gates

Open up to three additional ChatGPT chats only when a new architecture, strategy, experiment or deployment gate materially affects money/risk:

1. causal/statistical reviewer — future data, denominator, selection bias, censoring, stopping rules;
2. trading-economics reviewer — executable route, cost/slippage, opportunity yield, false positives/negatives;
3. minimum-engineering/runtime reviewer — append-only schema, bounded work, idempotency, SQLite contention, deployment acceptance.

These reviewers are not duplicate implementers. Each receives the same frozen handoff and returns an independent verdict. The lead synthesizes disagreements; Codex verifies claims against code/SQLite and integrates only accepted changes.

## Concurrency rules

- One dirty checkout has exactly **one writer**.
- Additional chats are read-only reviewers by default.
- True parallel code work requires isolated Git worktrees, disjoint file ownership, explicit interface contracts and one final integrator.
- Never start a second `codex exec resume` against an already running thread/worktree merely to inject a message.
- Never edit the same authority/continuity file concurrently.
- No commit or push without explicit user authorization. No Live activation.

## Communication contract

### Operational bidirectional channel

The routing pointer, not a display title, identifies the persistent pair:

- Codex execution thread: `01a0514b-bbb5-7400-baf9-d9feb4dc603d`.
- Lead ChatGPT conversation: read `coordination_mode.review_coordinator.conversation_id` from `CHATGPT_CODEX_SYNC_STATE.json`; current binding is `6a97a9c9-b0a4-83e8-b0d0-4840f4930990`.

Codex can start or resume the lead ChatGPT simply by calling `codex_app.send_message_to_thread` with that exact conversation id. Sending the prompt is the activation step; no separate browser launch, URL navigation, duplicate ChatGPT chat, `codex exec resume`, or long pasted context is required. ChatGPT uses the same app-thread channel to send a compact prompt to the exact Codex thread id.

Direct messages begin with `[GXH_SYNC_V2]` and use a compact envelope: `MESSAGE_ID`, `REPLY_TO` when applicable, `CYCLE_ID`, `FACT_CUTOFF_UTC`, `DELTA_SINCE`, `ISSUE_ID`, `TYPE`, `DECISION_REQUESTED`, `OWNER`, `BLOCKS_RELEASE`, `NEXT_SYNC_EVENT`, plus `ARTIFACT_POINTERS` instead of logs or diffs. A reply must echo `REPLY_TO` so concurrent questions cannot be crossed.

Use direct messaging for a release blocker, a question requiring a timely answer, a controlled deploy/restart boundary, a causal-hypothesis change, or the first material natural sample. Durable decisions, unresolved conflicts, version supersessions and handoffs are also appended to `CHATGPT_CODEX_SYNC.md` and reflected in the state pointer. Non-blocking ideas use the mailbox only and wait for a stable checkpoint.

If direct delivery fails, preserve the message in the mailbox, set `attention_required=true`, and continue only within the current safety/release boundary. Never inject a second `codex exec resume` into an active thread. Never select a replacement ChatGPT by title because duplicate titles and parallel chats exist. A new lead conversation is bound only by updating the exact id in the routing pointer with an explicit old→new handoff; historical lead ids remain evidence, not active destinations.

Only the designated lead sends implementation-facing synthesis to Codex. Parallel ChatGPT chats send role-stamped findings to the lead conversation or a referenced review artifact; they do not issue competing implementation instructions.

- Lead/reviewer findings are written to uniquely named files under `docs/PROJECT_CONTEXT/` with status `PENDING_CODEX_VERIFICATION`.
- `CHATGPT_REVIEW_PENDING.md` is a pointer, not an authority document.
- Codex must classify every material finding as `VERIFIED`, `DISPROVED` or `DEFERRED_WITH_BOUNDARY`, citing current code/tests/SQLite facts.
- A green test does not by itself close a semantic finding; the test must exercise the reviewed estimand and failure mode.
- Once resolved, Codex updates the current authority/context and may archive/remove the root pointer, preserving review evidence.

## Gate sequence

1. **Question gate:** define the exact estimand and why it could improve executable net EV.
2. **Registration gate:** freeze cohort, time clocks, queries, provider/surface, denominator and stop rules before natural samples.
3. **Implementation gate:** append-only/no-pollution behavior, strict point-in-time clocks, bounded work and restart recovery.
4. **Deployment gate:** targeted + relevant regression tests; live boundary re-query; one controlled restart; Paper/bridge/WAL health; Live locked.
5. **Maturity gate:** predefined sample/date/terminal coverage, no denominator loss and no repeated peeking-driven rule changes.
6. **Promotion gate:** only cost-adjusted executable Paper evidence can justify a separately reviewed production-threshold or Live proposal.

## Resource and model discipline

- Use the highest reasoning tier for strategy, causal design, money/risk, schema invariants and deployment gates.
- Use cheaper/faster Codex routing for mechanical edits, formatting, narrow tests and evidence extraction when risk is low.
- Do not multiply chats for throughput when the bottleneck is one dirty checkout or one live denominator.
- Prefer one strong objection that changes the design over ten broad reviews that restate context.

## Immediate project-specific boundary

For the active KOL token-addressability work:

- preserve the deployed legacy v1 registration and its natural rows;
- register corrected versions strictly forward;
- do not deploy the reviewed-defective route v1;
- keep every path `decision_eligible=0`, `affects=none` until a separate promotion gate;
- retain no-seed, ambiguity, missing, error and late outcomes in the denominator;
- never use eventual winners or future returns to select identifier, chain, pair or surface.
