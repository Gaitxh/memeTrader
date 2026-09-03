# GXH coin · ChatGPT ↔ Codex contact card

Status: `ACTIVE / GXH-C2C/1`

This is the smallest operational entry point for the persistent collaboration pair. It is routing metadata, not a product requirement, performance claim, or evidence ledger.

## Exact endpoints

- Codex execution thread: `01a0514b-bbb5-7400-baf9-d9feb4dc603d`
- Lead ChatGPT conversation: `6a98135b-e2d4-83e9-bd0c-269e36451542`
- ChatGPT project: `GXH coin`
- Fast routing pointer: `docs/PROJECT_CONTEXT/CHATGPT_CODEX_SYNC_STATE.json`
- Durable mailbox: `docs/PROJECT_CONTEXT/CHATGPT_CODEX_SYNC.md`
- Detailed state machine, readback, failover, multi-chat and idea-governance runbook: `docs/PROJECT_CONTEXT/CHATGPT_CODEX_BIDIRECTIONAL_CHANNEL.md`

Always re-read the fast routing pointer before sending. Exact IDs are authoritative; titles are not, because duplicate and parallel chats exist.

## How Codex starts or contacts the Lead ChatGPT

Use the Codex app tool `codex_app.send_message_to_thread` with the exact Lead ChatGPT conversation id from the routing pointer. Read the answer from that same conversation with `codex_app.read_thread`; while a response is still being generated, read again without resending the same `MESSAGE_ID`.

Sending one compact prompt is the activation step: it starts or resumes that ChatGPT conversation. No separate browser launch, URL navigation, duplicate chat, pasted project history, or `codex exec resume` is required.

Start the prompt with `[GXH_SYNC_V2]` and include only the useful delta:

```text
[GXH_SYNC_V2]
MESSAGE_ID: C2C-YYYYMMDD-HHMMSS-CODEX
REPLY_TO: <message id, or NONE>
TYPE: QUESTION | CHECKPOINT | BLOCKER | DEPLOY_GATE | NATURAL_SAMPLE | HANDOFF
CYCLE_ID: <active cycle>
FACT_CUTOFF_UTC: <timestamp>
DELTA_SINCE: <prior message/checkpoint>
ISSUE_ID: <stable dedupe key>
DECISION_REQUESTED: <one precise question or ACK_ONLY>
OWNER: Codex
BLOCKS_RELEASE: true | false
ARTIFACT_POINTERS: <small list of files/methods/test ids; never paste logs/diffs>
NEXT_SYNC_EVENT: <event that warrants another message>

DELTA:
<compact facts, uncertainty, and the smallest useful question>
```

A direct question must carry `MESSAGE_ID`; the answer must echo it in `REPLY_TO` so simultaneous reviews cannot be crossed.

## How ChatGPT contacts Codex

The Lead ChatGPT uses `codex_app.send_message_to_thread` with the exact Codex execution thread id. It follows the same envelope and sends only a consolidated implementation-facing synthesis. Reviewer chats do not send competing instructions to Codex; they route role-stamped findings to the Lead ChatGPT or a referenced review artifact.

## Direct message versus durable mailbox

Use a direct message for:

- a concrete release-blocking correctness, causality, safety, or production-contamination issue;
- a question that must be answered before the next implementation choice;
- a controlled deploy/restart boundary;
- evidence that changes the active causal hypothesis or priority;
- the first material natural cohort, terminal, or Paper result that changes interpretation.

Also append durable decisions, unresolved conflicts, version abandonment/supersession, and handoffs to `CHATGPT_CODEX_SYNC.md`, then update the fast pointer. Non-blocking ideas go to the mailbox/idea lane and wait for a stable checkpoint.

## Failure and recovery

If direct delivery fails:

1. append the compact message to the durable mailbox;
2. set `attention_required=true` in the routing pointer;
3. continue only within the already approved safety/release boundary;
4. do not start a second Codex writer or inject `codex exec resume` into the active thread.

If the Lead ChatGPT conversation is unavailable or full, record `CONTACT_REBIND_REQUIRED` once. A replacement becomes active only after an explicit old→new conversation-id handoff updates this card and the routing pointer. Current binding generation was explicitly moved on 2026-09-02 from `6a97a9c9-b0a4-83e8-b0d0-4840f4930990` to `6a98135b-e2d4-83e9-bd0c-269e36451542` after the new Lead restored E:-resident state and completed a verified bidirectional send/ACK cycle. Never guess a replacement by title.

## Scope and authority guard

Communication is an aid, not the objective. The execution order remains:

1. latest explicit user instruction and frozen safety rules;
2. root `AGENTS.md` frozen contract;
3. `CURRENT_OBJECTIVE_AND_PLAN.md` and `REQUIREMENT_LEDGER.md`;
4. current code, r6 SQLite, tests and runtime facts for factual verification;
5. ChatGPT/Codex/reviewer proposals only after verification and promotion.

The active checkout has one writer: Codex. The Lead ChatGPT reviews, challenges, researches and coordinates. No communication action may relax Strategy/evidence/risk gates, enable Live, backfill winners, mutate frozen registrations, expose secrets, or displace the active highest-impact bottleneck merely to improve the collaboration machinery.
