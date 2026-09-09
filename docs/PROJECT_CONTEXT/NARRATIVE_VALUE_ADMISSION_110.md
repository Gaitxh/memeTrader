# Narrative value admission110
REPLY_TO: C2C-20260909-NARRATIVE-VALUE-ADMISSION-110

## Implemented
Replace fixed150-second expensive research with actual settlement admission. Compatible open family positions must have principal_recovered=1, realized proceeds >= original positive stake, remaining raw>0, and a fresh visible exact original-pool mark (floor1000, positive finite price, observed<=recorded<=now, <=30s). Existing safety behavior must have no hard/soft hazards before dispatch.
Recovery is detected at the next existing15s low-priority pass, subject to held idle, shared slots/model policy/daily budget; no new event timer or synchronous Agent in settlement. No promise of immediate execution while core busy/budget exhausted.
Unrecovered cases remain reconsiderable. Compact transition counters VALUE_NOT_YET_RECOVERED/NO_CREDIBLE_LOCAL_EVENT/RECOVERY_TRIGGERED and other wait reasons are persisted only on transition/dispatch. Same reason does not generate repeated evidence. No quota spent or checkpoint consumed by wait.
The optional early-event branch is deliberately not enabled: existing local metadata/ambiguity memberships are untrusted, and no verified causal early-event producer is wired here. Do not describe this as validating absence of a real external event. Local leads are gathered only after research is otherwise admitted.
After first recovery dispatch, later checks at720/2700 seconds relative to research start require continued eligibility and previous EMERGING/CONFIRMED_EXPANDING. UNKNOWN/promotion/contradiction alone cannot cause another call. Per-case maximum3 dispatched/complete/interrupted checkpoints includes legacy attempts; daily4 calls/240k and60000 reservation unchanged. Interrupted recovery is not silently resent. Fresh research sources retain later local availability and cannot confirm at an earlier checkpoint.
No entry/exit policy, principal-recovered settlement authority or overlay extension rule changed. Existing project_doc_max_bytes=0 remains scoped to ephemeral AutonomousSearch.

## Validation
Existing narrative/local-lead suite plus value admission unit test:16 PASS. Added integration regression passes (targeted value subset2 PASS): repeated no-value passes spend0, later recovery dispatches once, reserve60000, no12m wait.17 distinct tests covered across these runs. git diff --check passes.
No forced Agent/transaction; no budget increase. Natural input-token/quality effect remains UNOBSERVED.

## Deployment boundary
Source implementation only for110. The immediately preceding scoped process-control action for109 was policy-rejected (blocked by policy); no alternate restart method attempted. Running initial109 c865f16 does not contain110 or final109 audit-label correction5c5424a. Do not claim110 active or token savings measured. Prior109 short held latency guard exceeded; future supported load requires fresh comparable health/held/passive acceptance. Preserve running funding/history/Live state.
