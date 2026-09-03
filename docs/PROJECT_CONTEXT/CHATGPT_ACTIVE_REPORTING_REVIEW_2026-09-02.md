# ChatGPT → Codex addressability reporting review · 2026-09-02

Status: `PENDING_CODEX_VERIFICATION`

Scope: newly added `kol_token_addressability_summary_from_connection()` and Web audit exposure.

## Blocking finding · current-version label with all-version counts

The new summary returns:

- `version = Store.KOL_TOKEN_ADDRESSABILITY_VERSION` (currently base v2), but
- `count(table)` uses unfiltered `SELECT COUNT(*)`, and
- `grouped(table,column)` groups all rows without a definition-version predicate.

The deployed r6 database already contains one immutable base-v1 admission/cohort/two milestones. After base v2 is registered, the current implementation would expose that legacy v1 cohort under a v2 label and mark v2 `observed` before v2 has any sample. This is denominator/version contamination.

## Required semantics

1. Base metrics (`admission_attempts`, `cohorts`, `milestones`, `ambiguities`, admission reasons) must filter `definition_version = current base version`.
2. Route/confirmation metrics must filter `definition_version = current route version` **and** the route definition must declare/join its compatible base cohort version.
3. Expose legacy versions separately, at minimum as `versions[]` or a `legacy` map containing registration, activation boundary and per-version immutable counts. Do not merge v1 and v2 into one denominator.
4. Status should distinguish at least:
   - `not_registered`;
   - `registered_waiting` (registered, zero current-version cohorts);
   - `observed` (current-version cohort exists);
   - `definition_invalid` / `incompatible_route_definition` when applicable.
5. Do not interpret a migration-added blank `definition_hash` on the legacy v1 row as captured evidence.
6. Summary code must fail closed if the relevant table/registration is absent or a frozen definition is malformed; it must not make the whole audit endpoint fail.

## Minimum regression test

Create one database containing:

- immutable legacy base-v1 registration + one admission/cohort/two milestones;
- current base-v2 registration with zero rows;
- no route registration.

Assert that:

- current v2 status is `registered_waiting` and current v2 cohort count is `0`;
- legacy v1 is shown separately with cohort count `1`;
- route status is `not_registered`;
- no legacy row appears in current-version reason/status counts.

Then append one v2 no-seed cohort and assert v2 alone becomes `observed` while v1 remains unchanged.
