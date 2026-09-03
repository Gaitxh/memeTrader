# Lead ChatGPT durable journal

Status: `ACTIVE / APPEND-ONLY INTENT`

Purpose: preserve project-relevant Lead ChatGPT conclusions, evidence pointers, hypotheses, contradictions and handoffs on `E:\memeTrader` so continuity does not depend on one ChatGPT or Codex conversation. This is not raw private reasoning, a trading evidence ledger, or authority over current code/SQLite/plan files.

## 2026-09-02 · collaboration-control-plane review

### User intent retained

- Final objective remains economic: make the system more likely to earn money in genuine forward operation, expressed as executable, cost-adjusted, risk-adjusted profitability rather than trade count or retrospective winners.
- The user explicitly wants Codex and ChatGPT to be able to wake/contact each other, discuss direction/ideas/research quickly, and use ChatGPT as the stronger research/reasoning layer while Codex retains execution strengths.
- Project-relevant Lead ChatGPT information that must survive chat/context loss should be persisted under `E:\memeTrader`.

### Current workspace findings

- `AGENTS.md` already contains a strong frozen contract, authority hierarchy, one-writer rule, requirement governance, bidirectional sync rules and exact contact-card requirement.
- `CHATGPT_CONTACT.md`, `CHATGPT_CODEX_SYNC_STATE.json`, `CHATGPT_CODEX_SYNC.md` and `CHATGPT_CODEX_BIDIRECTIONAL_CHANNEL.md` already implement a real direct/durable protocol. The durable mailbox contains a verified Codex acknowledgement that the direct `send_message_to_thread` target matched the designated Lead ChatGPT.
- The fast pointer currently names P0 cycle `kol-token-addressability-lag`; current code/data/plans override stale routing metadata.
- The local checkout is heavily dirty and two Codex processes were present at inspection time, so Lead ChatGPT must not create a competing business-code writer just to improve communication.
- Codex local diagnostics showed v0.147.0, model `gpt-5.6-sol`, stable/enabled hooks and memories, no configured global hooks, and no background app-server daemon. An update to 0.152.1 was reported available, but upgrading during active work is not justified solely for coordination.

### Root-cause interpretation for observed forgetting/drift

The project does not primarily lack memory documents. It already has them. The failure mode is that long-running Codex work can optimize a local explicit task under the global minimal-action policy without continuously reloading the project north star, active cycle and scope-change guard. Conversation compaction and supplementary prompts can therefore make a locally reasonable action globally wrong.

### Accepted design

Use a small collaboration control plane rather than more broad documentation:

1. `CHATGPT_LEAD_STATE.json` is a compact mutable Lead ChatGPT continuity snapshot on E:.
2. This journal records material Lead ChatGPT conclusions/handoffs durably without copying raw chain-of-thought.
3. A tiny E:-resident context guard will read the Lead state plus current `CHATGPT_CODEX_SYNC_STATE.json` and inject only compact context into Codex at session start/resume/compaction and prompt submission.
4. Direct messaging remains event-driven. A material blocker, changed causal hypothesis, deploy/restart gate, or first material natural sample justifies an immediate message; routine edits do not.
5. Codex remains the only active business-code/test/deploy writer. Reviewer chats remain read-only and report to the Lead.

### Current external capability verification

- Current Codex source exposes lifecycle hooks including `SessionStart`, `PostCompact` and `UserPromptSubmit`; SessionStart supports a compact source and can return additional developer context.
- Current Codex App Server exposes `thread/inject_items` for model-visible history without starting a user turn and `turn/steer` for an already active regular turn.
- These mechanisms are potentially a better real-time transport than file polling, but attaching a second app-server process to an already active Desktop thread has not been proven safe on this machine. Do not use it as the primary ChatGPT->Codex path until ownership/concurrency is validated.

### Drift gate to preserve

Before a local task is allowed to change active scope, ask: **Which currently observed end-to-end profitability bottleneck will this action change?** If there is no concrete answer tied to current evidence, preserve the idea but do not displace the active cycle.

### Next safe work

- Build and manually validate the read-only E:-resident context-guard script.
- Test hook execution in a non-writing Codex invocation before enabling it for active Desktop sessions.
- At a stable Codex checkpoint, have Codex consume the Lead state automatically; do not interrupt a live turn merely to acknowledge infrastructure.
- Explore direct App Server injection only after proving it cannot produce concurrent thread writers or corrupt rollout state.

## 2026-09-02 · full Codex-thread requirement archaeology

### Structured history recovered

The exact Codex thread `01a0514b-bbb5-7400-baf9-d9feb4dc603d` is available in the local Codex thread-history store. One chronological pass covered all 139 structured user messages. The same thread has 112 turns and 99 context compactions. This confirms that durable recovery does not need the user to manually export Markdown.

A sanitized synthesis is now stored in `CHATGPT_RECOVERED_USER_REQUIREMENTS_2026-09-02.md`. Do not persist secrets or raw private reasoning from the historical transcript.

### Repeated user instructions that deserve stronger enforcement

- Always keep the economic purpose and current execution direction explicit; supplementary requests must not silently replace the active plan.
- Avoid unnecessary defensive, review, audit and test work. The user explicitly corrected this behavior more than once.
- For generic tooling/implementation blockers, search official documentation, mature open-source projects, upstream issues/discussions and community operating experience before inventing a new subsystem.
- Route development work by task complexity and uncertainty so agentic cost is minimized without sacrificing completion, correctness or speed. Production memeTrader Agent routing and Codex-development Agent routing are separate concerns.
- Use high-intelligence ChatGPT collaboration for hard reasoning, architecture, causal/statistical design, trading economics, alternative paths and material gate review; do not use multiple Codex subagents as a substitute.
- Do not ask the user to perform operations Codex/ChatGPT can safely perform with current tools; request user action only when genuinely necessary.

### Development-side agent-cost signal

The target thread records 91 distinct `subAgentActivity(kind=started)` paths. A conservative name-only classification finds 48 started paths containing `audit`, `review` or `recheck`. This does not prove every such task was wasteful, but it is consistent with the user's repeated complaint that progress was slowed by excessive review/defensive work. `CHATGPT_CODEX_EXECUTION_EFFICIENCY_POLICY_2026-09-02.md` now separates development-agent routing from the production Agent budgets.

### Browser capture latency finding

Current extension code is not simply a one-minute poller: account and priority-post alarms are 30 seconds, DOM mutations schedule scan after about 750ms, heartbeat is 30 seconds, and the 60-second content `scan()` interval is fallback. Current live settings exposed 100 enabled accounts: 4 critical and 96 normal. With one rotating account tab and `critical, normal, critical` lanes, the idealized revisit interval is about three minutes per critical account and about 144 minutes for one full pass through all normal accounts.

This makes account/profile coverage scheduling a stronger candidate cause of stale/missed exact X capture than the fallback DOM scan. The user's request for faster capture should therefore be interpreted as an adaptive coverage/surge problem, not as a blind request to reduce every timer. Before implementation, Codex should verify current observation latency/miss denominators and then consider a value-weighted scheduler: exact priority posts and fresh high-impact episodes get surge treatment; critical accounts get short revisit; the large normal pool is sampled by forward source utility/priority with an exploration reserve.

Chrome's current documented alarm/service-worker behavior supports event/alarm-driven scheduling; service-worker interval timers are not a reliable substitute. Keep this as implementation guidance, not a new trading signal.

## 2026-09-02 21:58 +08:00 · direct ChatGPT→Codex delivery correction

The user correctly identified that the earlier Common Space/mailbox/hook work had **not** been proven to arrive as a realtime message in the active Codex turn. That distinction is now frozen: E:-resident files, `attention_required`, and hooks are continuity/visibility mechanisms; they do not by themselves prove direct delivery.

A direct path was then verified through the already-running Codex Desktop `codex_app` thread-management surface without starting a second implementation writer. ChatGPT sent `MESSAGE_ID=C2C-20260902-2149-LEAD-FORCE-SYNC-001` to the exact main Codex thread `01a0514b-bbb5-7400-baf9-d9feb4dc603d`. The send call returned success, and at `2026-09-02T13:58:52Z` the exact `MESSAGE_ID` and full payload were found in that target thread's structured rollout. This proves `DELIVERED`, not yet `ACKED`.

Going forward, communication status uses a hard evidence ladder: `RPC_ACCEPTED` only after the direct send returns success; `DELIVERED` only after the same unique `MESSAGE_ID` is visible in the exact target thread; `ACKED/REPLIED` only after Codex explicitly acknowledges/replies. Never claim that Codex incorporated a correction merely because a file was written or a direct call returned success. Detailed material stays in Common Space/E:; realtime messages remain short doorbells/pointers.
