# Codex: ChatGPT review routing pointer

This file is a compatibility entry point only. Do not maintain a second review checklist here.

To wake or message the designated Lead ChatGPT, start with `CHATGPT_CONTACT.md`. The current direct target and the compact `GXH-C2C/1` message envelope are maintained there; sending one message resumes that ChatGPT conversation. For review routing and durable replies:

1. Read `docs/PROJECT_CONTEXT/CHATGPT_CODEX_SYNC_STATE.json` first.
2. Open only the mailbox IDs and review files referenced by its current `open_groups`.
3. Append one consolidated Codex disposition to `docs/PROJECT_CONTEXT/CHATGPT_CODEX_SYNC.md`, then update the state pointer.

Do not cache a specific review/hold status in this compatibility file. Always use the current `CHATGPT_CODEX_SYNC_STATE.json` `active_cycle`, `attention_required`, and `open_groups`; when `attention_required=true`, read the referenced alert at the next stable checkpoint before changing scope. Current code, live SQLite, tests, processes, `CURRENT_OBJECTIVE_AND_PLAN.md`, `REQUIREMENT_LEDGER.md`, and `AGENTS.md` remain authoritative for implementation/runtime facts; review/Common-Space artifacts are verification and collaboration inputs, not authority overrides.
