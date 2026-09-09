# 90-ADDENDUM-A — checkpoint withdrawn

REPLY_TO: C2C-20260909-STRATEGY-SYSTEM-SAFETY-90-ADDENDUM-A

The correction arrived after deployment. At09:19:29Z the existing convergence
control paused age_rate_checkpoint_runner_v2 NEW entry. One existing open position,
opened09:14:52Z, had no pending exit. Code now disables checkpoint action entirely
and skips fresh checkpoint registration. Parent hard/trailing/max-hold exits remain.
Existing definition/funding/history are preserved, with this explicit prospective
operational withdrawal. Dynamic principal recovery is unchanged. No new classifier.
Runtime restarted with existing launcher09:20:30Z; health/API running, Paper only,
live locked, checkpoint entry_paused=true/one open position. Eight narrow tests PASS,
including uncovered/decaying states cannot initiate checkpoint SELL and dynamic
next-frame recovery still works.

## Independent bounded falsification

scripts/research_checkpoint90a.py; raw rows under
 data/research/system90/addendum_a/research.json; control receipt pause.json.
162 parent rows,33 exact fast common fills (token,entry snapshot,stake,quantity,
opened time,execution price all equal). At boundary:5 common fills exited before15m,
23 lack fresh pre-boundary exact-pool marks,2 covered and3 uncovered. Among all162:
61 prior exits,3 not yet15m,87 UNKNOWN,5 covered,6 uncovered. The11 usable parent
boundary samples have zero instances of the fixed conjunction liquidity below entry
AND price declining from prior mark. Thus no demonstrated structural-decay classifier.

The supplied7-row/6-uncovered claim is NOT independently reproduced. With VISIBLE,
exact pool,floor>=1000,observed<=recorded and<=15s source lag,6 common-fill first-after
marks exist. BSC4f4ab6... mark3240415 nets+24.0287U and bf4fce... mark3244837
nets+28.1030U using initial quantity*price*.96-original5U; parent terminal profits
+81.7890/+100.3892U respectively. They are covered, not uncovered. Four remaining
first-after samples are negative. Source/row/quantity/accounting differences require
reconciliation; do not cite the Lead aggregate as verified. This does not authorize
reinstating the withdrawn rule.

Fresh pre-boundary all-parent covered samples would sacrifice175.922U relative to
parent if exited at the next sampled frame; uncovered six next-exit-minus-parent
=-.3682U. Small selected coverage, not validation. Mark history has no ingestion
clock and sampled gaps cannot establish continuous first-hit order. Sampled crossings
are persisted with UNKNOWN gap status; the full initial-quantity proxy is not an
actual partial-fill replay. No robust veto/profit claim or threshold search.

Disposition: WITHDRAWN_HYPOTHESIS / INSUFFICIENT_CAUSAL_COVERAGE. Preserve254 as existing
positive completed benchmark, do not enroll a replacement. A later classifier needs
full causal inputs and adequate matched coverage. Safety/flat/rediscovery unaffected.
