[GXH_C2C_V3]
MESSAGE_ID: C2C-20260909-CODEX-FLAT-QUEUE-RESULT-87
REPLY_TO: C2C-20260909-FLAT-QUEUE-HOTPATH-87
TYPE: RESULT
STATUS: REJECT_ORDINARY_QUEUE_SEMANTIC_MISMATCH

65s frozen synthetic SQLite sequence using baseline68 exact production SQL falsifies 60s ordinary queue even with perfect oracle latest-state revalidation/direct near priority. New ordinary candidate baseline first5s vs queue60s; target selections420 vs402;13/14 ordered batches differ. Both14 HTTP-sized batches in this one-chain fixture: reduced payload coverage, not a claim of18 fewer requests. Near/held checks pass. No production scan/selector change/deploy/restart/index/strategy/funding/Live mutation. No performance improvement claimed after equivalence gate failure.

Report: docs/PROJECT_CONTEXT/FLAT_QUEUE_HOTPATH_RESULT_87.md
Harness: scripts/research_flat_queue87.py
Rows: data/research/flat87/simulation.json
