# Strategy behavior families method

Scope: 230 current effective Paper arms in `chain-meme-trader/funding-20260906-v002-final-1000` as of `2026-09-07T13:38:59.399800Z`. This is a read-only diagnostic; it does not claim alpha, create strategies, or interpret zero trades as invalidity.

## Sources and frontier

The base contract map is `RESOURCE_BOUND_STRATEGY_MAP.json` generated `2026-09-07T10:48:46.274606+00:00`. The frozen economics extract ends at `2026-09-06T16:46:50.205259Z`. The immutable diagnostic boundary fixes the as-of point and the trade frontier. Only `chain_meme_trader_policy_additions` marked `resource-bound/20260907-v1` and activated by the boundary are merged after that map. DB access uses SQLite `mode=ro` and `query_only=ON`; no Store constructor is used. Post-freeze observations are bounded by the frozen `entry_decisions` / `trades` row frontiers, the fixed trade frontier, and the same as-of timestamp.

## Definitions

* **Contract exact group**: same declared behavior-contract hash and normalized entry, exit, and Paper-execution fingerprints. It proves identical declared contract, not observed economic identity.
* **Actual dispatch fingerprint**: a normalized code-path classification (`main_snapshot_exact_family`, `main_snapshot_dex_visible`, isolated pattern/cohort, or the resource-bound isolated path), plus the admission fields consumed by that path. This prevents labels from substituting for dispatch evidence.
* **Economic family**: equal dispatch path/admission mechanism plus exit mechanism and execution economics. Exact groups can contain several arms; one family is one testable mechanism, not one independent sample.
* **Near duplicate**: same dispatch path, admission family and exit family but distinct one-or-more contract parameters. It is a structural warning, not proof that their realized outcomes match.
* **Same entry / different exit** and **different entry / same exit** compare full respective fingerprints. **Distinct** means neither structural relation holds in this map.
* **active** means forward-enabled and activated by the cutoff. **active_no_buy** means a recorded decision opportunity but no BUY. **dormant_coverage_unknown** means no decision record: it may be no trigger, no feature coverage, or an unobserved dispatcher path; it is never silently merged with another empty arm. **contaminated** requires a current-period accounting-contamination row.

Opportunity counts are unique `(token_id, shadow_cohort_id)` records. A Token/underlying opportunity observed by several arms remains one common opportunity when comparing arms; arm count must never be used as sample size. The CSV has both frozen evidence and post-freeze delta columns, preserving the coverage boundary.
