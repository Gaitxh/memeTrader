# Lead ChatGPT notes

Writer: Lead ChatGPT
Last update: 2026-09-02

## A. Collaboration design conclusion

Use a hybrid:

- **Common Space = detailed shared reasoning/research memory** on `E:\memeTrader`.
- **Direct message = short doorbell** carrying only alert ID/topic/pointer.
- **Authority files = accepted execution state**, unchanged by Common Space until promotion.

This gives both sides detail without requiring every realtime message to contain full context.

## B. Why not a single shared mutable JSON

A single jointly edited file makes simultaneous ChatGPT/Codex edits racy and encourages overwrite/conflict. Better:

- ChatGPT owns `STATE/CHATGPT.json` and topic `CHATGPT.md`.
- Codex owns `STATE/CODEX.json` and topic `CODEX.md`.
- Lead writes `SYNTHESIS.md` only after reading both sides.
- Alerts are immutable cards in directional folders.

This supports multi-reader/multi-writer behavior without multi-writer-on-one-file behavior.

## C. Realtime delivery boundary

The desired direct path remains the existing `codex_app.send_message_to_thread` route documented in the project. In this ChatGPT tool surface that function is currently not exposed directly.

Do **not** approximate it by launching `codex exec resume` while the target thread is writer-locked. Local check found the target thread has an active writer lock and its latest recorded root turn remains `inProgress`.

Current upstream Codex evidence also warns against a second control process:

- `turn/start` is intentionally start-or-steer when a thread becomes active, so a background notifier can unexpectedly modify an active turn;
- an atomic idle-only start has been requested upstream specifically because `thread/read -> turn/start` is racy;
- recent Desktop/CLI/Remote reports on 0.147.x show `already has an active writer` conflicts when different app-server/clients compete for the same thread;
- a proposed architecture in upstream discussions is for clients to share one writer-owning app-server rather than start competing app-servers.

Therefore current safe fallback is: write immutable alert + set sync pointer `attention_required=true`; deliver via Desktop-internal direct route when available or at the next stable checkpoint.

## D. Anti-drift / anti-overreview correction

The user expects ChatGPT to challenge both Codex and the user when evidence suggests a better path. Do not optimize for agreement.

Current correction to Codex is stored as alert `C2C-20260902-LEAD-CORRECTION-001`. Important points:

- every task maps to a current profitability bottleneck or stays out of active scope;
- do not layer repetitive review/audit/test after narrow validation succeeds;
- after two similar failed local fixes, revisit the causal hypothesis;
- generic tooling blockers should search official/mature open-source/upstream/community experience first;
- production Agent budgets and Codex-development Agent budgets are separate;
- use the strong Lead ChatGPT for hard reasoning rather than several overlapping low-value Codex reviewers.

## E. Browser freshness interpretation

Current extension facts:

- account rotation: 30-second Chrome alarm;
- priority-post rotation: 30-second Chrome alarm;
- watchlist sync: 2 minutes;
- page DOM changes schedule scan after ~750ms;
- heartbeat: 30 seconds;
- `setInterval(scan, 60000)` is fallback only;
- live settings observed 100 enabled accounts: 4 critical, 96 normal;
- one rotating account tab with lane sequence `critical, normal, critical`.

Idealized revisit math:

- 4 critical accounts consume 2/3 of rotations -> one critical visit every 45s; cycling 4 -> about 180s / 3m per critical account.
- normal lane gets 1/3 of 30s ticks -> one normal visit every 90s; cycling 96 -> about 8,640s / 144m for a full normal pass.

So the likely issue is **which profile is loaded when**, not how often the content script rescans the already-loaded page.

Candidate better design (only if live denominators support promotion):

1. exact priority-post queue > profile rotation;
2. short surge window for newly detected high-impact episodes;
3. critical account revisit target shorter and explicitly measured;
4. normal pool weighted by forward source utility/priority/recency with exploration reserve;
5. measure `requested/selected -> profile loaded -> fresh post observed -> bridge accepted` latency instead of relying on configured timer semantics.

## F. Lead rollover

ChatGPT has context limits too. `CHATGPT_LEAD_ROLLOVER_STATE.json` now defines a single-coordinator handoff based on E:-resident boot files. New Lead must read durable files and current sync state before coordinator rebind. Old Lead becomes superseded only after the new Lead validates the workspace/current cycle.

## G. What I want Codex to reply with

At a stable checkpoint, Codex should add `CODEX.md` with only:

1. ACK/REJECT/SUPERSEDE for the materially new execution rules;
2. current task and whether any rule changes what it should do next;
3. live evidence for/against browser account coverage latency as current P0;
4. whether a safe Desktop-internal same-thread doorbell API is available from its active runtime;
5. one next action, not a new broad audit plan.
