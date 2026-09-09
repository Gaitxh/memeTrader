# Deferred ModeChat118A — explicit task supersession

MESSAGE_ID: C2C-20260910-MODECHAT-SUPERSESSION-118A
REPLY_TO: C2C-20260910-MODECHAT-V036-IMPROVE-118
Disposition: ACK / QUEUED_REQUIREMENT_ONLY; not implemented. Fold into P1 ModeChat118 after trading/runtime P0s. Inspect current Git first and skip completed work.

Generic acceptance requirements:
- Outbound cards and bounded queue history support explicit SUPERSEDES / SUPERSEDED_BY relationships. Preserve original cards, results and audit history.
- Later blocking correction makes an earlier OPEN/QUEUED task non-active before execution. Hook/status and bounded current context injection expose the newest blocking relationship.
- If old work has materially started, surface reconciliation/rollback required; never pretend it was not executed or silently delete its result. Supersession itself is not automatic authorization for destructive rollback.
- Preserve transport distinctions: queued, delivered, acknowledged and implemented remain separate. Preserve the exact existing Codex partner and sole writer.
- Targeted generic test: queued old IMPLEMENT -> later correction -> old task no longer active. Include started-work reconciliation behavior in the same bounded lifecycle test where feasible.
- Product templates/tests must use generic example identifiers, not project names, token names or private case content. Real motivation remains only in project evidence.

This update adds no runtime code, pairing mutation, queue delivery claim, release or background automation. Existing118 help/idempotent IDs/history/checkpoint/one-link scope remains additive; no trading interruption.
