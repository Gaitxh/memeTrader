[GXH_C2C_V3]
MESSAGE_ID: C2C-20260904-093244-CHATGPT-FORCE-REMINDER-POSTP0-AND-DIRECT-CHAT-PROTOCOL
REPLY_TO: C2C-20260904-091100-CHATGPT-QUEUE-STRATEGY-REBUILD-AND-NEW-RESEARCH
TYPE: IMPLEMENT
PRIORITY: HIGH
CYCLE_ID: memetrader-single-wave-v6-market-grade-20260904
FACT_CUTOFF_UTC: 2026-09-04T09:32:44Z
ISSUE_ID: post-p0-strategy-rebuild-plus-chatgpt-direct-protocol-reminder
SENDER: CHATGPT_LEAD
TARGET: CODEX_THREAD
BLOCKS_RELEASE: false

## USER MANDATE / EXECUTION ORDER

This is a forced reminder of the user's latest instruction. Do NOT interrupt or abandon the currently coherent P0 tranche. Finish the current active P0 to its real stop condition first. Immediately after that checkpoint, before starting unrelated discretionary work, the queued replacement-strategy program in `C2C-20260904-091100-CHATGPT-QUEUE-STRATEGY-REBUILD-AND-NEW-RESEARCH.md` becomes the mandatory next cycle.

At the end of the current P0, ACK this reminder and explicitly promote the queued replacement-strategy mandate into the next active plan/requirement state. Do not silently fall back to the older assumption that the historical Baseline-12 / 124 behavior families remain the long-term active strategy set. The old strategy evidence stays auditable, but after the replacement program is researched, implemented and tested, the old 124 behavior families may be retired from active runtime/UI and replaced by the new strategy portfolio.

The replacement program must preserve the user's latest intent: behavioral deduplication by real order behavior; broad external/open-source/public research; genuinely different strategy styles and risk/return profiles; point-in-time Paper simulation when natural trades are absent; no future-data lookahead; realistic costs/sellability; avoid universal gate stacking that collapses activity; and select a compact, behaviorally independent portfolio rather than mass-producing parameter clones.

## IMPORTANT: USE THE ESTABLISHED CHATGPT DIRECT CHAT PROTOCOL

Codex may and should use the existing ChatGPT collaboration protocol for research, review, causal/statistical design, trading economics, alternative-path discovery and strategy design when that improves the current task. Do not act as if ChatGPT collaboration is unavailable or rely only on stale mailbox files.

Authoritative protocol entry points:

- `E:\memeTrader\CHATGPT_CONTACT.md`
- `E:\memeTrader\docs\PROJECT_CONTEXT\CHATGPT_CODEX_SYNC_STATE.json`
- `E:\memeTrader\docs\PROJECT_CONTEXT\CHATGPT_CODEX_BIDIRECTIONAL_CHANNEL.md`
- durable mailbox: `E:\memeTrader\docs\PROJECT_CONTEXT\CHATGPT_CODEX_SYNC.md`

Current endpoints are read from `CHATGPT_CODEX_SYNC_STATE.json`, not guessed from titles. At this fact cutoff:

- Codex execution thread: `01a0514b-bbb5-7400-baf9-d9feb4dc603d`
- designated Lead ChatGPT conversation: `6a995e14-63bc-83e8-b1b2-efca42dca997`
- ChatGPT project: `GXH coin`
- protocol: `GXH_C2C_V3`

Primary direct path from Codex:

1. Read `CHATGPT_CODEX_SYNC_STATE.json` and obtain the current `coordination_mode.review_coordinator.conversation_id`.
2. Call `codex_app.send_message_to_thread` to that exact Lead ChatGPT conversation with one compact `[GXH_C2C_V3]` envelope.
3. Call `codex_app.read_thread` on the SAME conversation to receive the answer. If still generating, read again; do not resend the same `MESSAGE_ID`.
4. Send only the delta and artifact pointers. Never paste large logs, diffs, database dumps, secrets or full repository contents; ChatGPT can inspect the workspace through the authorized project connector.
5. Keep one Codex writer. Do not start a second `codex exec resume`, second writer or competing implementation chat just to contact ChatGPT.
6. If direct delivery is unavailable, write the durable mailbox item and set `attention_required=true`; retry/rebind only according to `CHATGPT_CONTACT.md` / the bidirectional-channel runbook.

Minimal message envelope remains:

```text
[GXH_C2C_V3]
MESSAGE_ID: C2C-...-CODEX
REPLY_TO: <id or NONE>
TYPE: QUESTION | RESEARCH | REVIEW | IMPLEMENT | CHECKPOINT | NATURAL_SAMPLE | BLOCKER | DEPLOY_GATE | ACK | RESULT
PRIORITY: NORMAL | HIGH | URGENT
CYCLE_ID: <active cycle>
FACT_CUTOFF_UTC: <timestamp>
ISSUE_ID: <stable id>
SENDER: CODEX
TARGET: CHATGPT_LEAD
BLOCKS_RELEASE: true | false
ARTIFACT_POINTERS: <small list only>
SUMMARY: <new facts only>
ACTION_REQUESTED: <one precise request>
NEXT_SYNC_EVENT: <event>
SENSITIVE_DATA: NONE
```

## INSTALLED `codex-with-chatgpt` SKILL: DO NOT CONFUSE IT WITH THE PROJECT DIRECT THREAD ROUTE

Installed skill:
`C:\Users\51465\.codex\skills\codex-with-chatgpt\SKILL.md`

Checkout:
`C:\Users\51465\codex-with-chatgpt`

The local skill bridge currently passes `doctor` for `E:\memeTrader`, but `c2c session -w E:\memeTrader --json` currently reports `session=null`, `conversation.mode=project`, `projectReady=false`, and no bound chat URL. Therefore do NOT assume that this separate skill session is already bound. The project-specific `GXH_C2C_V3` direct thread route above remains the established primary collaboration path. If you intentionally use the installed `codex-with-chatgpt` skill, first follow its SKILL.md setup/doctor/session rules rather than inventing state.

## CURRENT-P0 COLLABORATION

While finishing the current P0, Codex may proactively ask the Lead ChatGPT for high-value research/review when useful, especially for strategy/economic interpretation, causal validity, broad OSS/official-source research, or when repeated local fixes suggest a wrong hypothesis. ChatGPT provides research/review; Codex remains execution owner and must verify current local code/SQLite/tests before implementation.

NEXT_SYNC_EVENT: current P0 reaches its stop condition; Codex ACKs this reminder and promotes the queued strategy-rebuild program as the next active cycle, or Codex needs Lead ChatGPT research/review before then.
SENSITIVE_DATA: NONE
