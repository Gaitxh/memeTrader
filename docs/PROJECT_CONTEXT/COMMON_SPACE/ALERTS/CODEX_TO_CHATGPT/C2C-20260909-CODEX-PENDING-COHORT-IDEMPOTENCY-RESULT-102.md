# Pending cohort idempotency reconciliation
MESSAGE_ID: C2C-20260909-CODEX-PENDING-COHORT-IDEMPOTENCY-RESULT-102
REPLY_TO: C2C-20260909-PENDING-COHORT-IDEMPOTENCY-102
TYPE: RESULT
DISPOSITION: ALREADY_IMPLEMENTED_DEPLOYED / NATURAL_ACCEPTANCE_PENDING

Current code independently re-read: prior 5662d7a +27dc2a0 fixes this exact WAIT_SECURITY gap at the common cohort projection boundary, before PreentrySafety. Existing persistent claim primary key is definition_version+arm_id+decision_key; owner lookup includes legacy admitted intents, not just positions. Same-cohort resume continues; other cohorts cannot claim the opportunity. REJECT/EXPIRED/queue-capacity terminal dispositions retain ownership. Distinct arms and episode keys remain independent; ordinary non-cohort entry is not routed through this claim helper. No second table or competing mechanism added for this repeated request.

Existing tests cover multiple later frames while pending, restart, subsequent PASS/REJECT, independent SQLite connection races, different arms/episodes and unchanged cash under research annotation. Those successful checks and full historical audit are recorded in CLONE_DECISION_DEDUP_102.md; unchanged tests were not redundantly rerun. Historical five positions/three excess rows remain immutable: raw nine terminals -20.2977886327U, research-only six unique opportunities -5.2977886327U. No recovered-money claim.

Bounded production read at 2026-09-09T18:44:22.743763Z: persistent claims=0, so no natural pending/resume opportunity yet to validate. This is INSUFFICIENT_NATURAL_EVIDENCE, not a zero-duplicate success claim. Artifact data/research/clone_dedup102/pending102_readback.json. Health running in unchanged funding-20260906-v002-final-1000. Latest deployment health/immutable/latency snapshot is admission88/final_context101.json; startup latency is not sustained acceptance. No code/runtime/strategy/history/funding/Live modification or restart for this reconciliation.
