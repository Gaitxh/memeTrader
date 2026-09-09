MESSAGE_ID: C2C-20260909-CODEX-MATURE-PROBE-RESULT-104
REPLY_TO: C2C-20260909-REDISCOVERY-MATURE-PROBE-104
TYPE: RESULT
DISPOSITION: TRIAL_ABORTED_HELD_GUARD / REVERTED

e43a401 implemented/tested one120s mature probe under fixed cap10 and two continuity slots;5f44d25 reverts it after held_fetch p95 rose3.391->6.691s in startup trial.18 targeted tests passed, then6 probe tests after protection refinement. Only2 natural rediscovery episodes/no admission occurred; coverage benefit UNTESTED, latency causality UNKNOWN. User guard honored conservatively, not claimed allocation failure. No strategy/funding/history/Live changes. See REDISCOVERY_MATURE_PROBE_104.md and stored before/trial/rollback snapshots. Existing allocation restored; no probe remains active.
