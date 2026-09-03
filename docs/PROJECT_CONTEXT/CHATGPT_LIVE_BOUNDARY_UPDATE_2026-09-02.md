# ChatGPT live boundary update · 2026-09-02

Status: `PENDING_CODEX_VERIFICATION`

This note supersedes only the earlier **zero-row factual snapshot**. It does not change any frozen definition or authorize mutation.

## Read-only r6 fact at the latest inspection

Database: `data/memetrader_forward_20260830_r6.sqlite3`

- max Observation id: `6445`;
- existing base registration: `kol-token-addressability-lag/v1`, activation Observation id `6435`;
- route registration/table: not yet present in the deployed database;
- v1 admission attempts: `1`;
- v1 cohorts: `1`;
- v1 milestones: `2`;
- route attempts/results/confirmation rows: not deployed;
- ambiguity table: not deployed.

The immutable v1 cohort is:

- Observation id `6441`, Event id `4665`;
- signal time `2026-09-02T05:14:24.940892Z`;
- configured source `x/@elonmusk`, priority `4`;
- event attention `22`;
- trigger is an Elon Musk post about a SpaceXAI browser/voice feature;
- `seed_status=no_seed_at_signal`, `identifiers_json=[]`;
- milestones: `signal/observed` and `explicit_identifier/missing_at_signal`;
- `decision_eligible=0`, `affects=none`.

Re-query all counts and the current max Observation immediately before any restart/registration.

## Consequences

1. **v1 is no longer a zero-sample definition.** Preserve its registration, admission, cohort and milestones exactly. Do not add the v2 `definition_hash` retroactively as if it had been captured by v1; a migration default may exist for schema compatibility but must not be interpreted as evidence.
2. Register base v2 with `activation_observation_id = max(observations.id)` inside the same short initialization transaction used for registration. It must admit only observations strictly after that boundary.
3. A route definition must explicitly declare the compatible base cohort definition/version, and every refresh/route query must filter on that version/hash. `cohort_id > activation_cohort_id` alone is insufficient and could process v1 or v2 rows under the wrong route semantics.
4. The currently coded `kol-token-addressability-route/v1` has not been deployed. Because its semantics are under active review, do not register it. Create a corrected route version only after the route review blockers are resolved.
5. The first natural cohort exposes the estimand distinction: the current denominator is **all eligible fresh high-priority low-attention KOL/social episodes**, including posts with no contemporaneous token intent. That is defensible only if summaries state that they estimate post→exact-CA/route conversion from the broad KOL-post population. Do not later remove unrelated/no-seed posts because no tradeable token appeared. If a token-intent-conditioned estimand is desired, it requires a separately preregistered, point-in-time classifier/definition and a new version—not post-hoc relabeling of v1/v2.
6. No-seed must remain in the denominator. Later exact-identifier discovery, if implemented, must be append-only with natural same-episode lineage; the immutable base cohort is not edited.

## Required deployment assertion

Before a controlled restart, tests and the deployment query must prove:

- old v1 row counts and bytes remain unchanged;
- new v2 activation is strictly after the then-current max Observation;
- route/refresh selects only the declared compatible base version;
- no route registration is created from the reviewed-defective route v1 constant;
- Paper remains operational and Live remains locked.
