# URGENT post-restart hold · 2026-09-02

Status: `P0_CODEX_ACTION_REQUIRED_BEFORE_MORE_ADDRESSABILITY_DEPLOYMENT`

This note records current read-only r6 facts **after** the controlled Runtime restart. It supersedes every earlier zero-sample statement.

## Current deployed facts

Read-only database: `data/memetrader_forward_20260830_r6.sqlite3`

At the inspection point:

- max Observation id: `6447`;
- legacy base v1 registration remains at activation Observation `6435`;
- legacy base v1 has exactly `1` admission, `1` cohort and `2` milestones;
- corrected base `kol-token-addressability-lag/v2-frozen-definition` registered at `2026-09-02T05:21:07.545226Z`, activation Observation `6445`;
- **reviewed-defective** `kol-token-addressability-route/v1` also registered at `2026-09-02T05:21:07.545373Z`, activation cohort id `1`;
- route v1 currently has `0` attempts, `0` results and `0` confirmation rows;
- base v2 currently has `0` admissions/cohorts/milestones at this inspection point;
- legacy cohort id `1` remains base v1 with a blank migration-added `definition_hash`; do not reinterpret that blank as captured evidence.

Re-query these counts immediately; the Runtime is active and new observations can arrive.

## Mandatory action

1. **Do not reinterpret or mutate route v1.** It is now an immutable registered version, even though it has zero route rows.
2. Treat route v1 as `registered_abandoned_before_first_attempt` (or equivalent explicit status) in documentation/reporting.
3. Stop route v1 from selecting any future cohort. The clean implementation is to advance the Runtime constant to a corrected route version whose strict registered definition declares the compatible base version/hash, after the blockers below are fixed. Do not alter the route-v1 registration row.
4. Every refresh/route query must require both:
   - cohort id strictly after the route registration boundary; and
   - `cohort.definition_version == route_definition.compatible_base_definition_version` (plus frozen definition hash when declared).
5. Register the corrected route version at the then-current maximum compatible base-v2 cohort id in the same short transaction. No historical backfill.
6. Before the next restart, preserve byte/count evidence for legacy base v1, base v2, and abandoned route v1 separately.

## Route-v1 blockers still open

These were documented before restart in `CHATGPT_ACTIVE_ROUTE_REVIEW_2026-09-02.md` and were not covered by the 12 green tests:

- request before deadline but provider completion after deadline can be counted timely;
- pair first available after deadline can be mislabeled queue delay;
- compatible base version is absent and cohort queries are not version-filtered;
- confirmation is only cross-origin exact-CA substring mention, not verified factual independence;
- no-seed cohorts cannot acquire a later naturally arrived exact identifier;
- surface-unmapped quote must not count same-surface success;
- periodic evidence scan remains unbounded at steady state;
- multi-version Web summary currently merges legacy rows under the current-version label.

## Operational boundary

This is not a request to stop the whole Paper system. Keep normal Paper capture/learning operating and Live locked. Only prevent the defective route-v1 definition from generating new experimental rows. No commit/push.
