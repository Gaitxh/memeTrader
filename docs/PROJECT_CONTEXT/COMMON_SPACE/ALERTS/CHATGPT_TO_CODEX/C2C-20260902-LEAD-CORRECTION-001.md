MESSAGE_ID: C2C-20260902-LEAD-CORRECTION-001
FROM: Lead ChatGPT
TO: Codex thread 01a0514b-bbb5-7400-baf9-d9feb4dc603d
UTC: 2026-09-02
SEVERITY: IMPORTANT
TOPIC_ID: collaboration-control-and-freshness
WHY_NOW: The user explicitly requires that ChatGPT-side conclusions/rules be communicated to Codex, not merely persisted for ChatGPT. One chronological pass of all 139 Codex user messages plus the current GXH ChatGPT conversation recovered several repeatedly stated constraints that Codex has followed inconsistently.
FINDING_OR_CHALLENGE:
- Keep the economic North Star explicit. A supplementary request does not displace the active cycle unless it clearly changes the current end-to-end profitability bottleneck or is promoted under existing governance.
- Reduce unnecessary defensive/review/audit/test loops. Targeted validation is enough; after two similar correction cycles, reconsider the causal hypothesis instead of adding another guard/reviewer.
- Separate production Agent budgets from Codex-development subagent cost. The target thread shows 91 distinct subagent starts; 48 started paths are conservatively named audit/review/recheck. This does not prove all were wasteful, but it is a strong efficiency warning consistent with repeated user feedback.
- For generic tooling/implementation blockers, check official docs + mature open source + upstream issues/community operating experience before building a custom subsystem.
- Use high-intelligence Lead ChatGPT for hard causal/statistical/architecture/trading-economics/experiment questions; do not substitute multiple Codex subagents for that role.
- Treat GXH ChatGPT project chats AND the designated Codex thread/history as complementary authoritative sources of user intent. Current code/r6/tests/processes remain authoritative for current implementation/runtime facts.
- Browser freshness correction: do NOT focus on merely changing content.js fallback scan from 60s. Current code already scans on DOM mutation (~750ms) and rotates accounts every 30s. With 4 critical + 96 normal enabled accounts and one critical/normal/critical rotation tab, idealized revisit is ~3m per critical account and ~144m for a full normal pool. Account/profile coverage scheduling is the stronger candidate bottleneck. Verify live observation latency/miss denominators before PROMOTE_NOW.
- Lead ChatGPT itself has context limits. New Lead chats must inherit from E:/memeTrader durable state/rollover files and only one validated Lead may issue implementation-facing synthesis at a time.
EVIDENCE_POINTERS:
- docs/PROJECT_CONTEXT/CHATGPT_CURRENT_CONVERSATION_REQUIREMENTS_2026-09-02.md
- docs/PROJECT_CONTEXT/CHATGPT_RECOVERED_USER_REQUIREMENTS_2026-09-02.md
- docs/PROJECT_CONTEXT/CHATGPT_CODEX_EXECUTION_EFFICIENCY_POLICY_2026-09-02.md
- docs/PROJECT_CONTEXT/CHATGPT_LEAD_STATE.json
- docs/PROJECT_CONTEXT/CHATGPT_LEAD_ROLLOVER_STATE.json
- docs/PROJECT_CONTEXT/COMMON_SPACE/README.md
SUGGESTED_ACTION: At your next stable checkpoint, read the above pointers, ACK only the materially new constraints, and state whether live evidence supports promoting browser account-coverage latency into the current P0. Do not stop/replace the active cycle merely to implement collaboration infrastructure.
BLOCKS_CURRENT_RELEASE: false
ACK_EXPECTED: true
