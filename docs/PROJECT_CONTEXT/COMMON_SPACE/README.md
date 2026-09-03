# GXH ChatGPT ↔ Codex Common Space

Status: `ACTIVE / COLLABORATION WORKSPACE / NOT EXECUTION AUTHORITY`

Root: `E:\memeTrader\docs\PROJECT_CONTEXT\COMMON_SPACE`

Purpose: a detailed shared reasoning/research workspace that both the designated Lead ChatGPT and the designated Codex execution thread can read at any time. It is where either side can record a better idea, challenge the other's current path, add evidence pointers, compare alternatives, or leave a detailed issue for the other side. **Realtime messages are the doorbell; Common Space is the room.**

This space complements, but never replaces, the authoritative execution files:

- `AGENTS.md`
- `docs/PROJECT_CONTEXT/CURRENT_OBJECTIVE_AND_PLAN.md`
- `docs/PROJECT_CONTEXT/REQUIREMENT_LEDGER.md`
- `docs/PROJECT_CONTEXT/CHATGPT_CODEX_SYNC_STATE.json`
- current code / r6 SQLite / tests / running-process facts

A proposal in Common Space does **not** change active scope until it is promoted through the existing governance rule.

## 1. Layout and writer ownership

```text
COMMON_SPACE/
  README.md
  STATE/
    CHATGPT.json        # ChatGPT-owned current collaborative state
    CODEX.json          # Codex-owned current collaborative state
  TOPICS/
    <topic-id>/
      README.md         # stable problem statement / shared pointers
      CHATGPT.md        # ChatGPT-owned detailed findings/proposals
      CODEX.md          # Codex-owned detailed findings/implementation facts
      SYNTHESIS.md      # Lead-owned synthesis after reading both sides
  ALERTS/
    CHATGPT_TO_CODEX/
      <message-id>.md   # immutable alert card
    CODEX_TO_CHATGPT/
      <message-id>.md   # immutable alert card
```

Writer ownership avoids the most common multi-agent failure: both sides editing the same JSON/paragraph and overwriting each other. Everyone may read everything. Each side writes its own STATE/notes. `SYNTHESIS.md` is Lead ChatGPT-owned unless an explicit handoff says otherwise.

Topic `README.md` should be edited only at a stable checkpoint; routine debate belongs in the side-specific files.

## 2. What belongs here

Good Common Space content:

- a causal hypothesis and how to falsify it;
- a better implementation/tool/open-source path;
- a contradiction in the other side's current reasoning;
- live evidence pointers and what they imply;
- architecture/experiment/trading-economics alternatives;
- a short cost/benefit comparison;
- a user requirement that appears lost or misinterpreted;
- an unresolved question that matters to the active bottleneck;
- a proposed change in priority, with the bottleneck it would change.

Do **not** put here:

- secrets, wallet material, cookies, tokens or credentials;
- raw private chain-of-thought;
- large logs, full diffs or copied code bodies when a file/query pointer is enough;
- every routine test/edit/status update;
- final trading decisions or a shadow ledger that belongs in SQLite;
- a second `CURRENT_OBJECTIVE_AND_PLAN`.

## 3. Alert card protocol

When one side sees a material problem or clearly better path, create one small immutable card in its outgoing alert folder. Suggested fields:

```text
MESSAGE_ID:
FROM:
TO:
UTC:
SEVERITY: INFO | IMPORTANT | BLOCKER
TOPIC_ID:
WHY_NOW:
FINDING_OR_CHALLENGE:
EVIDENCE_POINTERS:
SUGGESTED_ACTION:
BLOCKS_CURRENT_RELEASE: true|false
ACK_EXPECTED: true|false
```

Then use the fastest available direct transport to send only a short doorbell, for example:

`COMMON_SPACE_ALERT C2C-... -> docs/PROJECT_CONTEXT/COMMON_SPACE/ALERTS/CHATGPT_TO_CODEX/<id>.md`

If direct transport is unavailable, the existing durable mailbox/pointer remains the fallback.

Do not resend the same alert unless materially new evidence exists. ACK may be a direct short message plus a pointer to the receiver's topic note; it does not require editing the sender's immutable alert.

## 4. When to interrupt the other side

Interrupt immediately only for:

- current direction appears to violate North Star / active cycle / frozen rule;
- new evidence changes the causal hypothesis or priority;
- a clearly better OSS/tool/architecture path materially reduces time/cost/risk;
- material experiment/strategy/trading-economics issue;
- first important natural sample changes interpretation;
- controlled deploy/restart/release gate;
- two similar failed attempts indicate the local hypothesis is wrong;
- new user instruction changes a frozen rule or authority.

Do not interrupt for routine reads, edits, passing tests, document formatting, or information that can wait until the next stable checkpoint.

## 5. Topic lifecycle

1. Create a topic only when it maps to a real project bottleneck or collaboration problem.
2. Each side adds only new information to its own note.
3. Lead ChatGPT periodically synthesizes disagreement/decision-relevant delta.
4. If the topic changes active execution, promote the accepted result into Objective/Requirement/Sync authority.
5. Close the topic when its falsifiable question is answered or its decision is promoted/rejected.
6. Do not keep polishing a closed topic.

## 6. Chat rollover and Common Space

A new Lead ChatGPT must read `CHATGPT_LEAD_ROLLOVER_STATE.json` and its mandatory boot set. Common Space is then used to recover active detailed discussions that were too rich for the rollover checkpoint.

A new Codex context/compaction should read its own `STATE/CODEX.json`, the Lead state, current sync pointer, and only the Common Space topics referenced by the current active cycle or pending alert.

This prevents both extremes: losing detail, or injecting the entire project history on every turn.

## 7. Efficiency guard

Common Space must reduce duplicated reasoning, not create bureaucracy. If a direct 2-line message is enough, do not open a topic. If a topic exists, do not create another one for the same question. If the accepted answer is already in an authority file, link it and close the topic.
